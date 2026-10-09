import json
import logging
import pika
from django.conf import settings
from django.db import DatabaseError
from billing.models import Reading
from got.serializers import ConnectionGotSerializer
from got.models import OrderForm
from order.models import Order

logger = logging.getLogger(__name__)


def _build_address_str(obj):
    """Build address string from flat address fields (address_street, address_street_number, etc.)."""
    if not obj:
        return None
    address_parts = []
    if obj.address_street:
        street_str = ""
        if obj.address_street.type:
            street_str += f"{obj.address_street.type.name} "
        if obj.address_street.name:
            street_str += obj.address_street.name
        if street_str:
            address_parts.append(street_str.strip())
    if obj.address_street_number:
        number_str = ""
        if obj.address_street_number.number_type:
            if obj.address_street_number.number_type.type == 'N':
                number_str = str(obj.address_street_number.number) if obj.address_street_number.number else ""
            elif obj.address_street_number.number_type.type == 'SN':
                number_str = "S/N"
            elif obj.address_street_number.number_type.type == 'R':
                number_str = f"{obj.address_street_number.number}-{obj.address_street_number.number_end}"
            elif obj.address_street_number.number_type.type == 'S':
                number_str = f"{obj.address_street_number.number} {obj.address_street_number.number_suffix}"
        if number_str:
            address_parts.append(number_str)
    if obj.address_postal_code:
        address_parts.append(obj.address_postal_code.code)
    if obj.address_city:
        address_parts.append(obj.address_city.name)
    return ", ".join(address_parts) if address_parts else None


def _format_decimal(value):
    """Formata un Decimal per enviar-lo com a text: 1000.00 -> '1000', 25.50 -> '25.5'."""
    if value is None:
        return None
    text = f"{value:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _resolve_order_supply_point(order):
    """
    Punt de subministrament de l'ordre: primer el de la propia ordre i, si no en
    te, el del contracte. Es retorna None si cap dels dos hi es.
    """
    if order.supply_point_id:
        return order.supply_point
    if order.contract_id and order.contract and order.contract.supply_point_default_id:
        return order.contract.supply_point_default
    return None


def _resolve_exploitation_token(order):
    """
    Resol el token de l'Exploitation associada a l'ordre.

    Ordre de prioritat:
        1. Order -> SupplyPoint -> Connection -> Exploitation
        2. Order -> Contract -> SupplyPoint -> Connection -> Exploitation
        3. Order -> Connection -> Exploitation
        4. Order -> ConnectionRequest -> Exploitation

    No es tenen en compte l'address ni les coordenades de l'ordre: Exploitation no
    te cap camp geoespacial ni cap relacio amb Address, de manera que no hi ha cap
    ruta fiable per resoldre'l en aquells casos.

    Retorna None si no es resol.
    """
    # SupplyPoints que cal provar (l'ordre encara que no en tingui el del contracte).
    supply_points = []
    if order.supply_point_id:
        supply_points.append(order.supply_point)
    if order.contract_id and order.contract and order.contract.supply_point_default_id:
        supply_points.append(order.contract.supply_point_default)

    # Connection i ConnectionRequest tenen el FK a Exploitation directament;
    # els SupplyPoint hi arriben a través de la seva Connection.
    holders = [sp.connection for sp in supply_points if sp.connection_id]
    if order.connection_id:
        holders.append(order.connection)
    if order.connection_request_id:
        holders.append(order.connection_request)

    for holder in holders:
        if holder.exploitation_id:
            exploitation = holder.exploitation
            if exploitation and exploitation.token:
                return exploitation.token
    return None


def _get_last_reading_info(supply_point):
    """
    Última lectura REAL del comptador del punt de subministrament.

    Només es tenen en compte lectures reals (is_estimated=False), en linea amb el
    que ja fa la CRM a service/serializers/supply_point_serializer.py.

    Retorna {"value", "date", "consumption"}, amb tots els valors a None si no hi ha
    comptador o si no hi ha cap lectura real.
    """
    empty = {"value": None, "date": None, "consumption": None}

    # Sense comptador no hi ha lectura. Aquest guarda-també evita que passar
    # meter=None al filtre esdevingui un "meter_id IS NULL" que podria retornar
    # una lectura d'un punt de subministrament sense comptador.
    if not supply_point or not supply_point.meter_id:
        return empty

    try:
        # Filtre per supply_point i meter alhora: son els dos primers camps de
        # l'index reading_prev_no_contract_idx, de manera que l'ordenació per
        # -reading_date resol l'última lectura directament de l'index (amb el
        # desempata -id, el Postgres 13+ afegeix un sort incremental només del
        # grup empatat). copied_from__isnull=True descarta les lectures copiades
        # que genera el fanout dels comptadors generals: aquí ens interessa la
        # lectura física del comptador, no les còpies per contracte.
        reading = (
            Reading.objects.filter(
                supply_point=supply_point,
                meter=supply_point.meter,
                is_active=True,
                is_estimated=False,
                copied_from__isnull=True,
            )
            .order_by("-reading_date", "-id")
            .first()
        )
    except DatabaseError:
        # Només es toleren errors de base de dades (connexió caiguda, timeout...).
        # Els errors de programació (FieldError per un camp mal escrit, TypeError,
        # AttributeError...) no es silencien: es propagen perquè es detectin
        # immediatament enlloc d'enviar sempre None a la GMAO.
        logger.exception(
            "No s'ha pogut llegir l'última lectura del SP %s", supply_point.pk
        )
        return empty

    if not reading:
        return empty

    # El consum ve de calculated_value: el consum del tram respecte a
    # previous_reading (docs/agent/readings.md), és a dir reading_value -
    # previous.reading_value. Si és null, s'envia null i no es cau mai a
    # real_consumption.
    consumption = reading.calculated_value
    return {
        "value": _format_decimal(reading.reading_value),
        "date": (
            reading.reading_date.strftime("%Y-%m-%d")
            if reading.reading_date
            else None
        ),
        "consumption": (
            f"{_format_decimal(consumption)}m3"
            if consumption is not None
            else None
        ),
    }


def _get_connection():
    """
    Create a blocking connection to RabbitMQ using Pika.
    """
    # Parse URL: amqp://user:pass@host:port/%2f
    url = settings.RABBITMQ_URL

    # Use pika's URLParameters for parsing
    parameters = pika.URLParameters(url)
    parameters.heartbeat = 30
    parameters.blocked_connection_timeout = 300

    return pika.BlockingConnection(parameters)


def publish_event(key: str, payload: dict):
    """
    Publica un esdeveniment a RabbitMQ (queue: crm-event)

    Args:
        key: Tipus d'esdeveniment (ex: "order.created") - s'inclou al payload
        payload: El contingut del missatge com a diccionari

    Si INSTANCE_UID esta definit, s'afegeix el camp "instance_uid" al payload:
    GMAO l'ha d'usar com a routing key per respondre a l'exchange d'entrada
    (gmao-events-exchange). Si no esta definit, el missatge es igual que abans.
    """
    if not settings.RABBITMQ_ENABLED:
        return  # RabbitMQ deshabilitat per aquest client

    # Add event type and instance UID to payload
    payload["key"] = key
    if settings.INSTANCE_UID:
        payload["instance_uid"] = settings.INSTANCE_UID

    # Ensure payload is JSON serializable
    try:
        message_body = json.dumps(payload, ensure_ascii=False,indent=2, default=str)
    except TypeError as e:
        logger.error(f"Payload not JSON serializable: {payload}")
        raise ValueError(f"Payload contains non-serializable objects: {e}")

    # Log the formatted message payload we are trying to send
    logger.info(f"Preparing to send RabbitMQ event '{key}' with payload: {message_body}")

    connection = None
    try:
        connection = _get_connection()
        channel = connection.channel()

        # Declare the queue (creates it if it doesn't exist)
        channel.queue_declare(queue=settings.RABBIT_OUT_QUEUE, durable=True)

        properties_kwargs = {
            "delivery_mode": 2,
            "content_type": "application/json",
            "content_encoding": "utf-8",
        }
        if settings.INSTANCE_UID:
            properties_kwargs.update(
                app_id=settings.INSTANCE_UID,
                headers={"instance_uid": settings.INSTANCE_UID},
                reply_to=settings.INSTANCE_UID,
            )

        # Publish the message
        channel.basic_publish(
            exchange="", 
            routing_key=settings.RABBIT_OUT_QUEUE,
            body=message_body,
            properties=pika.BasicProperties(**properties_kwargs),
        )
        logger.info(f"Published {key} to {settings.RABBIT_OUT_QUEUE}")

    except Exception as e:
        logger.error(f"Failed to publish RabbitMQ event '{key}'. Payload was: {message_body}. Error: {e}")
        raise

    finally:
        if connection and connection.is_open:
            connection.close()


def publish_order_created(order: Order):
    """
    Publica un esdeveniment quan es crea una nova Order

    Args:
        order: Instància del model Order
    """
    # Resolve customer details (fallback to connection_request person)
    customer_name = None
    customer_email = None
    customer_phone = None

    if order.contract and order.contract.holder:
        customer_name = f"{order.contract.holder.name} {order.contract.holder.surname}".strip()
    elif order.connection_request and order.connection_request.person:
        person = order.connection_request.person
        customer_name = f"{person.name} {person.surname if person.surname else ''}".strip()

    if order.contract and order.contract.person_contact_email:
        customer_email = order.contract.person_contact_email.email
        customer_phone = order.contract.person_contact_email.phone
    elif order.connection_request and order.connection_request.person:
        default_contact = order.connection_request.person.contacts.filter(is_default=True).first()
        if default_contact:
            customer_email = default_contact.email
            customer_phone = default_contact.phone

    # Contexte addicional per a la GMAO
    supply_point = _resolve_order_supply_point(order)
    exploitation_token = _resolve_exploitation_token(order)
    last_reading = _get_last_reading_info(supply_point)

    payload = {
        "event_id": f"order:{order.pk}:created",
        "order_id": order.pk,
        "order_token": order.token,
        "description": order.description if order.description else None,
        "status": order.status.name if order.status else None,
        "status_token": order.status.token if order.status else None,
        "type": order.type.name if order.type else None,
        "type_token": order.type.token if order.type else None,
        "reason": order.reason.name if order.reason else None,
        "reason_token": order.reason.token if order.reason else None,
        "priority": order.priority.token if order.priority else None,
        "address_str": str(order.address) if order.address else None,
        "supply_point_address": (
            str(order.supply_point.address)
            if order.supply_point and order.supply_point.address
            else None
        ),
        "connection_address": (
            ConnectionGotSerializer(order.connection).data["address"]
            if order.connection
            else None
        ),
        "connection_request_address": _build_address_str(order.connection_request),
        "contract_token": order.contract.token if order.contract else None,
        "exploitation_token": exploitation_token,
        "due_date": order.dueDateAt.isoformat() if order.dueDateAt else None,
        "form_structure_name": (
            OrderForm.objects.filter(order_type=order.type).first().name
            if order.type and OrderForm.objects.filter(order_type=order.type).exists()
            else None
        ),
        "form_structure": (
            OrderForm.objects.filter(order_type=order.type).first().structure
            if order.type and OrderForm.objects.filter(order_type=order.type).exists()
            else None
        ),
        "long": str(order.longitude) if order.longitude else None,
        "lat": str(order.latitude) if order.latitude else None,
        "additional_info": [
            {
                "key": "customer_name",
                "text": customer_name,
            },
            {
                "key": "customer_email",
                "text": customer_email,
            },
            {
                "key": "customer_phone",
                "text": customer_phone,
            },
            {
                "key": "incident_token",
                "text": order.incident.token if order.incident else None,
            },
            {
                "key": "incident_description",
                "text": order.incident.description if order.incident else None,
            },
            {
                "key": "claim_request_token",
                "text": order.claim_request.token if order.claim_request else None,
            },
            {
                "key": "claim_request_description",
                "text": order.claim_request.description if order.claim_request else None,
            },
            {
                "key": "contract_token",
                "text": order.contract.token if order.contract else None,
            },
            {
                "key": "connection_use_type",
                "text": order.connection.use_type.name if order.connection and order.connection.use_type else None,
            },
            {
                "key": "connection_supply_type_name",
                "text": order.connection.supply_type.name if order.connection and order.connection.supply_type else None,
            },
            {
                "key": "connection_material_name",
                "text": order.connection.material.name if order.connection and order.connection.material else None,
            },
            {
                "key": "connection_diameter_name",
                "text": order.connection.diameter.name if order.connection and order.connection.diameter else None,
            },
            {
                "key": "connection_valve_type_name",
                "text": order.connection.valve_type.name if order.connection and order.connection.valve_type else None,
            },
            {
                "key": "connection_installation_at",
                "text": order.connection.installation_at.isoformat() if order.connection and order.connection.installation_at else None,
            },
            {
                "key": "connection_dma_name",
                "text": order.connection.dma.name if order.connection and order.connection.dma else None,
            },
            {
                "key": "connection_request_token",
                "text": order.connection_request.token if order.connection_request else None,
            },
            {
                "key": "connection_request_use_type",
                "text": order.connection_request.use_type.name if order.connection_request and order.connection_request.use_type else None,
            },
            {
                "key": "connection_request_type_name",
                "text": order.connection_request.type.name if order.connection_request and order.connection_request.type else None,
            },
            {
                "key": "connection_request_installation_type",
                "text": order.connection_request.installation_type.name if order.connection_request and order.connection_request.installation_type else None,
            },
            {
                "key": "connection_request_material_name",
                "text": order.connection_request.material.name if order.connection_request and order.connection_request.material else None,
            },
            {
                "key": "connection_request_diameter_name",
                "text": order.connection_request.diameter.name if order.connection_request and order.connection_request.diameter else None,
            },
            {
                "key": "connection_request_valve_type_name",
                "text": order.connection_request.valve_type.name if order.connection_request and order.connection_request.valve_type else None,
            },
            {
                "key": "connection_request_dma_name",
                "text": order.connection_request.dma.name if order.connection_request and order.connection_request.dma else None,
            },
            {
                "key": "supply_point_token",
                "text": order.supply_point.token if order.supply_point else None,
            },
            {
                "key": "supply_point_name",
                "text": order.supply_point.name if order.supply_point else None,
            },
            {
                "key": "supply_point_cadastral",
                "text": order.supply_point.cadastral if order.supply_point else None,
            },
            {
                "key": "supply_point_installation_at",
                "text": order.supply_point.installation_at.isoformat() if order.supply_point and order.supply_point.installation_at else None,
            },
            {
                "key": "supply_point_type_name",
                "text": order.supply_point.type.name if order.supply_point and order.supply_point.type else None,
            },
            {
                "key": "supply_point_status_name",
                "text": order.supply_point.status.name if order.supply_point and order.supply_point.status else None,
            },
            {
                "key": "supply_point_supply_type_name",
                "text": order.supply_point.supply_type.name if order.supply_point and order.supply_point.supply_type else None,
            },
            {
                "key": "supply_point_is_potable",
                "text": order.supply_point.is_potable if order.supply_point else None,
            },
            {
                "key": "supply_point_meter_token",
                "text": order.supply_point.meter.token if order.supply_point and order.supply_point.meter else None,
            },
            {
                "key": "supply_point_meter_code",
                "text": order.supply_point.meter.code if order.supply_point and order.supply_point.meter else None,
            },
            {
                "key": "supply_point_meter_manufacturer",
                "text": order.supply_point.meter.manufacturer if order.supply_point and order.supply_point.meter else None,
            },
            {
                "key": "supply_point_meter_model",
                "text": order.supply_point.meter.model if order.supply_point and order.supply_point.meter else None,
            },
            {
                "key": "supply_point_meter_installation_at",
                "text": order.supply_point.meter.installation_at.isoformat() if order.supply_point and order.supply_point.meter and order.supply_point.meter.installation_at else None,
            },
            {
                "key": "supply_point_meter_status_name",
                "text": order.supply_point.meter.status.name if order.supply_point and order.supply_point.meter and order.supply_point.meter.status else None,
            },
            {
                "key": "last_reading_value",
                "text": last_reading["value"],
            },
            {
                "key": "last_reading_date",
                "text": last_reading["date"],
            },
            {
                "key": "last_reading_consumption",
                "text": last_reading["consumption"],
            },
        ]
    }

    if order.type and order.type.gmao_department_token:
        payload["gmao_department_token"] = order.type.gmao_department_token

    publish_event("order.created", payload)


def publish_observation_created(observation):
    """
    Publica un esdeveniment quan es crea una nova OrderObservation

    Args:
        observation: Instància del model OrderObservation
    """
    payload = {
        "order_token": observation.order.token if observation.order else None,
        "message": observation.observation,
        "created_at": observation.created_at.isoformat() if observation.created_at else None,
    }
    publish_event("observation.created", payload)


def publish_order_invalidation_event(order):
    """
    Publica un esdeveniment per invalidar una Order

    Args:
        order: Instància del model Order
    """
    payload = {
        "order_token": order.token,
    }
    publish_event("order.invalidated", payload)


# def publish_order_updated(order):
#     """
#     Publica un esdeveniment quan s'actualitza una Order

#     Args:
#         order: Instància del model Order
#     """
#     payload = {
#         "event_id": f"order:{order.pk}:updated",
#         "order_id": order.pk,
#         "description": order.description if order.description else None,
#         "order_token": order.token,
#         "status": order.status.name if order.status else None,
#         "status_token": order.status.token if order.status else None,
#         "type": order.type.name if order.type else None,
#         "type_token": order.type.token if order.type else None,
#         "reason": order.reason.name if order.reason else None,
#         "reason_token": order.reason.token if order.reason else None,
#         "address_id": order.address.pk if order.address else None,
#         "address_str": str(order.address) if order.address else None,
#         "supply_point_id": order.supply_point.pk if order.supply_point else None,
#         "supply_point_address": (
#             str(order.supply_point.address)
#             if order.supply_point and order.supply_point.address
#             else None
#         ),
#         "connection_id": order.connection.pk if order.connection else None,
#         "connection_address": (
#             ConnectionGotSerializer(order.connection).data["address"]
#             if order.connection
#             else None
#         ),
#         "contract_id": order.contract.pk if order.contract else None,
#         "contract_token": order.contract.token if order.contract else None,
#         "contract_request_id": (
#             order.contract_request.pk if order.contract_request else None
#         ),
#         "due_date": order.dueDateAt.isoformat() if order.dueDateAt else None,
#         "timestamp": order.created_at.isoformat() if order.created_at else None,
#         "operators_id": list(order.operators.values_list("pk", flat=True)),
#         "operators_token": list(order.operators.values_list("token", flat=True)),
#         "operators_name": list(order.operators.values_list("name", flat=True)),
#         "operators_email": list(order.operators.values_list("email", flat=True)),
#         "form_structure": (
#             OrderForm.objects.filter(order_type=order.type).first().structure
#             if order.type and OrderForm.objects.filter(order_type=order.type).exists()
#             else None
#         ),
#         "long": str(order.longitude) if order.longitude else None,
#         "lat": str(order.latitude) if order.latitude else None
#     }
#     publish_event("order.updated", payload)


# def publish_order_completed(order):
#     """
#     Publica un esdeveniment quan es completa una Order

#     Args:
#         order: Instància del model Order
#     """
#     payload = {
#         "event_id": f"order:{order.pk}:completed",
#         "order_id": order.pk,
#         "order_token": order.token,
#         "status": order.status.name if order.status else None,
#         "status_token": order.status.token if order.status else None,
#         "completed_at": order.completed_at.isoformat() if order.completed_at else None,
#         "timestamp": order.updated_at.isoformat() if order.updated_at else None,
#     }
#     publish_event("order.completed", payload)
