# contract/utils/contract_request_service.py

import datetime
import uuid
import logging
from django.db import transaction
from django.utils.translation import gettext as _
from django.core.exceptions import ObjectDoesNotExist
from contract.models import Contract, ContractRequest, ContractRequestStatus, ContractStatus, ContractTerminationRequest, ContractTerminationStatus, PaymentType
from order.models import Order, OrderType, OrderStatus
from logger.models import LogContractRequestStatus
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token
from order.utils.claim_request_order_service import get_order_type_initials
from contract.utils.contract_service import contract_create  # Add this import at the top
from service.models import MeterStatus, SupplyPointStatus

logger = logging.getLogger(__name__)

# v--- Descomenta aquest codi per habilitar el logging a la consola --v
#
# Configure logger to output messages to the console
# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# console_handler.setFormatter(formatter)
# logger.addHandler(console_handler)
# logger.setLevel(logging.DEBUG)


def contract_request_finalize(user, contract_request_id):
    """
    Finalitza un ContractRequest canviant el seu estat a 'pendent' segons la configuració del projecte
    i generant les Orders corresponents basades en els order_types associats.

    Args:
        contract_request_id (int): L'ID del ContractRequest a finalitzar.

    Returns:
        ContractRequest: L'objecte ContractRequest actualitzat.

    Raises:
        ContractRequest.DoesNotExist: Si no es troba un ContractRequest amb l'ID proporcionat.
        ConfigProject.DoesNotExist: Si no es troba la configuració requerida en ConfigProject.
        ContractRequestStatus.DoesNotExist: Si no es troba un ContractRequestStatus amb el token obtingut.
        OrderStatus.DoesNotExist: Si no es troba l'OrderStatus 'PENDING'.
        Exception: Per qualsevol altre error que pugui sorgir durant l'operació.
    """
    try:
        with transaction.atomic():
            print(1)
            # 1. Obtenir el ContractRequest
            contract_request = ContractRequest.objects.select_related('status', 'supply_point_default').get(id=contract_request_id)
            logger.info(f"ContractRequest {contract_request_id} obtingut correctament.")
            
            print(2)
            # 2. Obtenir el pending_token des de ConfigProject
            try:
                pending_token_config = ConfigProject.objects.get(token='contract_request_pending_token')
                pending_token = pending_token_config.value
                logger.info(f"Pending token obtingut: {pending_token}")
            except ObjectDoesNotExist:
                logger.error("ConfigProject amb token 'contract_request_pending_token' no existeix.")
                raise ObjectDoesNotExist("ConfigProject amb token 'contract_request_pending_token' no existeix.")
            
            print(3)
            # 3. Obtenir el ContractRequestStatus amb el token obtingut
            try:
                pending_status = ContractRequestStatus.objects.get(token=pending_token)
                logger.info(f"ContractRequestStatus amb token '{pending_token}' obtingut correctament.")
            except ObjectDoesNotExist:
                logger.error(f"ContractRequestStatus amb token '{pending_token}' no existeix.")
                raise ObjectDoesNotExist(f"ContractRequestStatus amb token '{pending_token}' no existeix.")
            
            print(4)
            # 4. Assignar el nou estat al ContractRequest
            contract_request.status = pending_status
            contract_request.save()
            logger.info(f"ContractRequest {contract_request_id} actualitzat al status '{pending_status.name}'.")
            
            print(4.2)
            # 4.2. Guardem el canvi de status a LogContractRequestStatus
            LogContractRequestStatus.objects.create(
                object=contract_request,
                previous_status=contract_request.status,
                current_status=pending_status,
                observation=None,
                user=user  # Replace with the actual user if available
            )
            logger.info(f"LogContractRequestStatus creat per ContractRequest {contract_request_id}.")
            
            print(5)
            # 5. Obtenir l'OrderStatus 'PENDING'
            try:
                order_pending_token_config = ConfigProject.objects.get(token='order_status_pending_token')
                order_pending_token = order_pending_token_config.value
                pending_order_status = OrderStatus.objects.get(token=order_pending_token)
                logger.info(f"OrderStatus 'PENDING' obtingut correctament. Token { pending_order_status.token }" )
            except ObjectDoesNotExist:
                logger.error("OrderStatus amb token 'PENDING' no existeix.")
                raise ObjectDoesNotExist("OrderStatus amb token 'PENDING' no existeix.")
            
            print(6)
            # 6. Generar les Orders corresponents basades en els order_types
            order_types = contract_request.order_types.all()
            if not order_types.exists():
                logger.warning(f"ContractRequest {contract_request_id} no té order_types associats.")
            
            for order_type in order_types:
              # Obtenir les inicials del tipus d'ordre
              order_type_initials = get_order_type_initials(order_type.token) if order_type.token else 'OR'
              
              # Generar token amb format: {yymmdd}/{prefix_objecte}{id_objecte}/{inicials_tipus_ordre}{id_incremental}
              # Per contract_request, afegim CR{id} per poder agrupar les ordres del mateix CR
              # Utilitzem generate_token però afegim els separadors "/" manualment
              now = datetime.datetime.now()
              date_part = now.strftime("%y%m%d")
              last_instance = Order.objects.order_by('-id').first()
              next_id = (last_instance.id if last_instance else 0) + 1
              id_part = f'{next_id:03d}'[-3:]
              token = f"{date_part}/CR{contract_request_id}/{order_type_initials}{id_part}"
              #if contract request does not have the orders with the same order type, create a new order
              if not contract_request.orders.filter(type=order_type).exists():
                new_order, _ = Order.objects.get_or_create(
                    token=token,  # Generar un token únic
                    contract_request=contract_request,
                    type=order_type,
                    status=pending_order_status,
                    supply_point=contract_request.supply_point_default,
                    # Assignar altres camps necessaris segons el teu model Order
                    # Per exemple, assegura't que 'address' pot ser null si és necessari
                )
                # Associar la Order al ContractRequest via el ManyToManyField
                contract_request.orders.add(new_order)
                logger.info(f"Order {new_order.id} creada per ContractRequest {contract_request_id} i OrderType {order_type.id}.")
                
            
            # Si hi ha un contract.contract_request_termination, hem de mirar si hi ha alguna Order associada a la baixa.
            if hasattr(contract_request, 'contract_termination_requests'):
                termination_orders = []
                for contract_termination_request in contract_request.contract_termination_requests.all():
                    termination_orders.extend(contract_termination_request.orders.all())
                for order in termination_orders:
                    order.status = pending_order_status
                    order.save()

            
            # Per finalitzar, mirem si hi ha ordres de treball. Perquè si no hi ha ordres de treball, directament passarem a generar el contracte
            contract_request_check_orders(user, contract_request.id)

            return contract_request

    except ContractRequest.DoesNotExist:
        logger.error(f"ContractRequest amb id {contract_request_id} no existeix.")
        raise
    except ConfigProject.DoesNotExist as e:
        logger.error(str(e))
        raise
    except ContractRequestStatus.DoesNotExist as e:
        logger.error(str(e))
        raise
    except OrderStatus.DoesNotExist as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.exception(f"Ha ocorregut un error en finalitzar el ContractRequest {contract_request_id}.")
        raise


def contract_request_finalize_in_place(user, contract_request_id):
    """
    Com contract_request_finalize, però un cop generades les Order pendents
    (per traçabilitat/historial) NO espera que es completin: finalitza el
    ContractRequest i crea el Contract immediatament. Les Order generades es
    deixen en el seu estat pendent normal (no es marquen com a completades).
    Pensat per a fluxos que no requereixen cap intervenció física (p. ex.
    canvi de nom mantenint el mateix codi de contracte).
    """
    try:
        with transaction.atomic():
            contract_request = ContractRequest.objects.select_related('status', 'supply_point_default').get(id=contract_request_id)
            logger.info(f"ContractRequest {contract_request_id} obtingut correctament.")

            try:
                pending_token_config = ConfigProject.objects.get(token='contract_request_pending_token')
                pending_token = pending_token_config.value
            except ObjectDoesNotExist:
                logger.error("ConfigProject amb token 'contract_request_pending_token' no existeix.")
                raise ObjectDoesNotExist("ConfigProject amb token 'contract_request_pending_token' no existeix.")

            try:
                pending_status = ContractRequestStatus.objects.get(token=pending_token)
            except ObjectDoesNotExist:
                logger.error(f"ContractRequestStatus amb token '{pending_token}' no existeix.")
                raise ObjectDoesNotExist(f"ContractRequestStatus amb token '{pending_token}' no existeix.")

            contract_request.status = pending_status
            contract_request.save()

            LogContractRequestStatus.objects.create(
                object=contract_request,
                previous_status=contract_request.status,
                current_status=pending_status,
                observation=None,
                user=user
            )

            try:
                order_pending_token_config = ConfigProject.objects.get(token='order_status_pending_token')
                order_pending_token = order_pending_token_config.value
                pending_order_status = OrderStatus.objects.get(token=order_pending_token)
            except ObjectDoesNotExist:
                logger.error("OrderStatus amb token 'PENDING' no existeix.")
                raise ObjectDoesNotExist("OrderStatus amb token 'PENDING' no existeix.")

            order_types = contract_request.order_types.all()
            for order_type in order_types:
                order_type_initials = get_order_type_initials(order_type.token) if order_type.token else 'OR'
                now = datetime.datetime.now()
                date_part = now.strftime("%y%m%d")
                last_instance = Order.objects.order_by('-id').first()
                next_id = (last_instance.id if last_instance else 0) + 1
                id_part = f'{next_id:03d}'[-3:]
                token = f"{date_part}/CR{contract_request_id}/{order_type_initials}{id_part}"
                if not contract_request.orders.filter(type=order_type).exists():
                    new_order, _ = Order.objects.get_or_create(
                        token=token,
                        contract_request=contract_request,
                        type=order_type,
                        status=pending_order_status,
                        supply_point=contract_request.supply_point_default,
                    )
                    contract_request.orders.add(new_order)
                    logger.info(f"Order {new_order.id} creada per ContractRequest {contract_request_id} i OrderType {order_type.id}.")

            if hasattr(contract_request, 'contract_termination_requests'):
                termination_orders = []
                for contract_termination_request in contract_request.contract_termination_requests.all():
                    termination_orders.extend(contract_termination_request.orders.all())
                for order in termination_orders:
                    order.status = pending_order_status
                    order.save()

            # A diferència de contract_request_finalize, no esperem que les Order
            # es completin: finalitzem el ContractRequest i creem el Contract ara mateix.
            contract_request_finalize_token_config = ConfigProject.objects.get(token='contract_request_finalize_token')
            contract_request_change_status(user, contract_request, contract_request_finalize_token_config.value)
            contract_create(user, contract_request_id)

            return ContractRequest.objects.get(id=contract_request_id)

    except ContractRequest.DoesNotExist:
        logger.error(f"ContractRequest amb id {contract_request_id} no existeix.")
        raise
    except ConfigProject.DoesNotExist as e:
        logger.error(str(e))
        raise
    except ContractRequestStatus.DoesNotExist as e:
        logger.error(str(e))
        raise
    except OrderStatus.DoesNotExist as e:
        logger.error(str(e))
        raise
    except Exception as e:
        logger.exception(f"Ha ocorregut un error en finalitzar en lloc el ContractRequest {contract_request_id}.")
        raise


def contract_request_check_orders(user, contract_request_id):
    try:
        with transaction.atomic():
            message =  None
            # 1. Obtenir el ContractRequest
            contract_request = ContractRequest.objects.select_related('status').get(id=contract_request_id)
            logger.info(f"ContractRequest {contract_request_id} obtingut correctament.")

            # 2. Obtenir el pending_token des de ConfigProject
            try:
                pending_token_config = ConfigProject.objects.get(token='contract_request_pending_token')
                pending_token = pending_token_config.value
                logger.info(f"Pending token obtingut: {pending_token}")
            except ObjectDoesNotExist:
                logger.error("ConfigProject amb token 'contract_request_pending_token' no existeix.")
                raise ObjectDoesNotExist("ConfigProject amb token 'contract_request_pending_token' no existeix.")
            
            # 2.2. Obtenir el completed_token des de ConfigProject
            try:
                order_completed_token_config = ConfigProject.objects.get(token='order_status_completed_token')
                order_completed_token = order_completed_token_config.value
            except ObjectDoesNotExist:
                logger.error("ConfigProject amb token 'contract_request_pending_token' no existeix.")
                raise ObjectDoesNotExist("ConfigProject amb token 'contract_request_pending_token' no existeix.")
            

            # 3. Implementar la verificació de les ordres
            # Obtenir totes les ordres relacionades
            orders = contract_request.orders.select_related('status')
            logger.info(f"ContractRequest té { len(orders) } orders.")

            # Verificar si totes les ordres tenen el token completat
            all_finalized = True
            for order in orders:
                logger.info(f"ContractRequest: mirem order { order.id  } i el seu status token és: { order.status.token }.")
                if order.status.token != order_completed_token:
                    logger.info(f"ContractRequest: order id: { order.id  } el seu token no és finalitzat (token finalitzat és: { order_completed_token }). all_finalized = False ")
                    all_finalized = False
                    break
            
            if all_finalized and contract_request.status.token == pending_token:
                logger.info(f"ContractRequest: Totes les `Orders` finalitzades")
                # 4. Actualitzar l'estat del ContractRequest
                contract_request_finalize_token_config = ConfigProject.objects.get(token='contract_request_finalize_token')
                contract_request_change_status(user, contract_request, contract_request_finalize_token_config.value)
                # 5. Creem el contracte
                contract_create(user, contract_request_id)
                message = {"message": "Sol·licitud finalitzada correctament, contracte creat", "status": "success"}
            else:
                logger.info(f"ContractRequest: Algunes de les `Orders` no estan finalitzades. No es pot completar el ContractRequest.")
            
            return message

    except ContractRequest.DoesNotExist:
        logger.error(f"ContractRequest amb id {contract_request_id} no existeix.")
        raise
    except ConfigProject.DoesNotExist as e:
        logger.error(str(e))
        raise
    except ContractRequestStatus.DoesNotExist as e:
        logger.error(str(e))
        raise
    except OrderStatus.DoesNotExist as e:
        logger.error(str(e))
        raise      
    except Exception as e:
        logger.exception(f"Ha ocorregut un error en finalitzar el ContractRequest {contract_request_id}.")
        raise
    
def check_and_deactivate_supply_point_and_meter(contract_termination):
    """
    Comprova si el punt de subministrament i el comptador vinculats a la sol·licitud de baixa es poden donar de baixa
    i els desactiva si no hi ha altres contractes actius o sol·licituds pendents.
    """
    readings = contract_termination.readings.all()
    if not readings.exists():
        logger.warning(f"No hi ha lectures per a la sol·licitud de baixa {contract_termination.id}. No es pot donar de baixa el comptador.")
        return

    last_reading = readings.order_by('-reading_date').first()
    contract = contract_termination.contract
    supply_points = contract.supply_points.all()
    
    try:
        active_contract_status_token = ConfigProject.objects.get(token='contract_active_token').value
        meter_inactive_status_token = ConfigProject.objects.get(token='meter_status_inactive_token').value
        meter_inactive_status = MeterStatus.objects.get(token=meter_inactive_status_token)
        
        supply_point_inactive_status_token = ConfigProject.objects.get(token='supply_point_status_deactivate_token').value
        supply_point_inactive_status = SupplyPointStatus.objects.get(is_default=True) # changed to default, do not deactivate but change to pending
        
        # Tokens de sol·licitud no obertes (finalitzades o cancel·lades)
        try:
            finalize_token = ConfigProject.objects.get(token='contract_request_finalize_token').value
        except ConfigProject.DoesNotExist:
            finalize_token = "3"
        
        try:
            cancel_token = ConfigProject.objects.get(token='contract_request_cancel_token').value
        except ConfigProject.DoesNotExist:
            cancel_token = None
            
    except (ConfigProject.DoesNotExist, MeterStatus.DoesNotExist) as e:
        logger.error(f"Configuració faltant per donar de baixa el comptador: {str(e)}")
        return

    for supply_point in supply_points:
        meter = supply_point.meter
        if not meter:
            continue

        # 1. Comprovar si hi ha altres contractes actius per aquest supply point
        other_active_contracts = Contract.objects.filter(
            supply_points=supply_point,
            status__token=active_contract_status_token,
            is_active=True
        )
        
        # 2. Comprovar si hi ha sol·licituds de contracte pendents per aquest supply point
        pending_contract_requests = ContractRequest.objects.filter(
            supply_points=supply_point,
            is_active=True
        ).exclude(status__token=finalize_token)
        
        if cancel_token:
            pending_contract_requests = pending_contract_requests.exclude(status__token=cancel_token)
        
        if not other_active_contracts.exists() and not pending_contract_requests.exists():
            if meter:
                meter.status = meter_inactive_status
                meter.uninstallation_at = last_reading.reading_date
                meter.save()
                logger.info(f"Comptador {meter.code} donat de baixa per finalització de contracte {contract.token}. Data uninstallation: {meter.uninstallation_at}")
            
            supply_point.status = supply_point_inactive_status
            supply_point.removal_at = last_reading.reading_date
            supply_point.save()
            logger.info(f"Punt de subministrament {supply_point.token} donat de baixa per finalització de contracte {contract.token}. Data removal: {supply_point.removal_at}")

def contract_termination_check_orders(user, contract_termination_id):
    try:
        with transaction.atomic():
            message = None
            # 1. Obtenir el ContractRequest
            contract_termination = ContractTerminationRequest.objects.select_related('status').get(id=contract_termination_id)
            logger.info(f"ContractRequest {contract_termination_id} obtingut correctament.")

            # 2. Obtenir el pending_token des de ConfigProject
            try:
                pending_token_config = ConfigProject.objects.get(token='contract_termination_pending_token')
                pending_token = pending_token_config.value
                logger.info(f"Pending token obtingut: {pending_token}")
            except ObjectDoesNotExist:
                logger.error("ConfigProject amb token 'contract_request_pending_token' no existeix.")
                raise ObjectDoesNotExist("ConfigProject amb token 'contract_request_pending_token' no existeix.")
            
            # 2.2. Obtenir el completed_token des de ConfigProject
            try:
                order_completed_token_config = ConfigProject.objects.get(token='order_status_completed_token')
                order_completed_token = order_completed_token_config.value
            except ObjectDoesNotExist:
                logger.error("ConfigProject amb token 'contract_request_pending_token' no existeix.")
                raise ObjectDoesNotExist("ConfigProject amb token 'contract_request_pending_token' no existeix.")
            

            # 3. Implementar la verificació de les ordres
            # Obtenir totes les ordres relacionades
            orders = contract_termination.orders.select_related('status')
            logger.info(f"ContractTerminationRequest té { len(orders) } orders.")

            # Verificar si totes les ordres tenen el token completat
            all_finalized = True
            for order in orders:
                logger.info(f"ContractTerminationRequest: mirem order { order.id  } i el seu status token és: { order.status.token }.")
                if order.status.token != order_completed_token:
                    logger.info(f"CnontractTerminationRequest: order id: { order.id  } el seu token no és finalitzat (token finalitzat és: { order_completed_token }). all_finalized = False ")
                    all_finalized = False
                    break
            
            if all_finalized and contract_termination.status.token == pending_token:
                logger.info(f"ContractTerminationRequest: Totes les `Orders` finalitzades")
                # 4. Actualitzar l'estat del ContractRequest
                contract_cancel_token_config = ConfigProject.objects.get(token='contract_terminated_status')
                contract_termination_request_finalize_token_config = ConfigProject.objects.get(token='contract_termination_completed_token')
                contract_termination_request_change_status(user, contract_termination, contract_termination_request_finalize_token_config.value)
                contract_termination.approved_at = datetime.datetime.now()
                contract_termination.contract.status = ContractStatus.objects.get(token=contract_cancel_token_config.value)
                contract_termination.contract.save()
                contract_termination.save()

                # Donar de baixa el punt i el comptador si hi ha una lectura de baixa i no hi ha altres contractes/sol·licituds
                check_and_deactivate_supply_point_and_meter(contract_termination)



                message = {"message": "Sol·licitud de baixa finalitzada correctament", "status": "success"}
            else:
                logger.info(f"ContractTerminationRequest: Algunes de les `Orders` no estan finalitzades. No es pot completar el ContractRequest.")
            
            return message


    except ContractRequest.DoesNotExist:
        logger.error(f"ContractTerminationRequest amb id {contract_termination_id} no existeix.")
        raise
    except ConfigProject.DoesNotExist as e:
        logger.error(str(e))
        raise
    except ContractRequestStatus.DoesNotExist as e:
        logger.error(str(e))
        raise
    except OrderStatus.DoesNotExist as e:
        logger.error(str(e))
        raise      
    except Exception as e:
        logger.exception(f"Ha ocorregut un error en finalitzar el ContractTerminationRequest {contract_termination_id}.")
        raise

def contract_request_change_status(user, contract_request, new_status_token):
    try:
        # Obtenir el nou status basat en el token
        new_status = ContractRequestStatus.objects.get(token=new_status_token)
        
        # Guardar l'estat anterior
        previous_status = contract_request.status
        
        # Canviar l'estat del ContractRequest
        contract_request.status = new_status
        contract_request.save()
        
        # Crear un registre del canvi d'estat
        LogContractRequestStatus.objects.create(
            object=contract_request,
            previous_status=previous_status,
            current_status=new_status,
            observation="",
            user=user
        )
        
        logger.info(f"ContractRequest {contract_request.id} canviat de '{previous_status.name}' a '{new_status.name}'.")
        
    except ContractRequestStatus.DoesNotExist:
        logger.error(f"ContractRequestStatus amb token '{new_status_token}' no existeix.")
        raise
    except Exception as e:
        logger.exception(f"Error en canviar l'estat del ContractRequest {contract_request.id}: {str(e)}")
        raise

def contract_termination_request_change_status(user, contract_termination, new_status_token):
    try:
        # Obtenir el nou status basat en el token
        new_status = ContractTerminationStatus.objects.get(token=new_status_token)
        
        # Guardar l'estat anterior
        previous_status = contract_termination.status
        
        # Canviar l'estat del ContractRequest
        contract_termination.status = new_status
        contract_termination.save()
        
        # Crear un registre del canvi d'estat
        # TODO logger
        
        logger.info(f"ContractRequest {contract_termination.id} canviat de '{previous_status.name}' a '{new_status.name}'.")
        
    except ContractRequestStatus.DoesNotExist:
        logger.error(f"ContractRequestStatus amb token '{new_status_token}' no existeix.")
        raise
    except Exception as e:
        logger.exception(f"Error en canviar l'estat del ContractRequest {contract_termination.id}: {str(e)}")
        raise

def contract_request_validate_data(contract_request):
    """
    Valida que la sol·licitud de contracte tingui totes les dades necessàries
    per poder crear un contracte.
    Retorna una llista de cadenes de text amb els errors de validació trobats.
    """
    errors = []

    # 1. Validació del titular (holder)
    holder = contract_request.holder
    if not holder:
        errors.append("Falta el titular de la sol·licitud.")
    else:
        if not holder.token:
            errors.append("El titular ha de tenir un NIF/DNI informat.")
        if not holder.name:
            errors.append("El titular ha de tenir un nom informat.")
        if not holder.is_juridic and not holder.surname:
            errors.append("El titular ha de tenir els cognoms informats.")

    # 2. Validació del punt de subministrament
    if not contract_request.supply_point_default:
        errors.append("Falta el punt de subministrament per defecte de la sol·licitud.")
    elif contract_request.meter_mode != 'none' and not contract_request.supply_point_default.meter:
        errors.append(_("Falta assignar un comptador al punt de subministrament de la sol·licitud."))

    # 3. Validació del tipus de sol·licitud
    if not contract_request.type:
        errors.append("Falta el tipus de sol·licitud de contracte.")

    # 4. Validació de la data de registre / alta
    if not contract_request.registration_date:
        errors.append("Falta la data de registre/alta.")

    # 5. Validació de l'adreça de facturació
    address_billing = contract_request.address_billing
    if not address_billing:
        errors.append("Falta l'adreça de facturació de la sol·licitud.")
    else:
        addr = address_billing.address
        if not addr:
            errors.append("L'adreça de facturació no té informació d'adreça vinculada.")
        else:
            if not addr.is_manual:
                if not addr.street:
                    errors.append("Falta el carrer de l'adreça de facturació.")
                elif not addr.street.name:
                    errors.append("El carrer de l'adreça de facturació no té nom informat.")
                
                if not addr.street_number:
                    errors.append("Falta el número de carrer de l'adreça de facturació.")
                else:
                    # Validació segons les regles de carrerer d'AGENTS.md
                    # N: número, SN: sense número, R: rang de números, S: número amb sufix
                    snum = addr.street_number
                    if snum.number_type:
                        ntype = snum.number_type.type
                        if ntype in ['N', 'R', 'S'] and snum.number is None and not snum.number_suffix:
                            errors.append("L'adreça de facturació té un tipus de número que requereix especificar un número o sufix.")
            
            if not addr.postal_code:
                errors.append("Falta el codi postal de l'adreça de facturació.")
            
            if not addr.city and not addr.city_name:
                errors.append("Falta la població de l'adreça de facturació.")
            
            if not addr.province and not addr.province_name:
                errors.append("Falta la província de l'adreça de facturació.")
            
            if not addr.country:
                errors.append("Falta el país de l'adreça de facturació.")

    # 6. Validació del mètode de pagament
    payment = contract_request.payment
    if not payment:
        errors.append("Falta el mètode de pagament de la sol·licitud.")
    else:
        if not payment.type:
            errors.append("Falta especificar el tipus de pagament.")
        elif payment.type.token == 'DIRECT_DEBIT':
            iban_obj = payment.IBAN
            if not iban_obj:
                errors.append("El pagament per domiciliació bancària (SEPA) requereix una compta bancària (IBAN) vinculada.")
            else:
                if not iban_obj.iban:
                    errors.append("El codi IBAN està buit.")
                if not iban_obj.swift:
                    errors.append("Falta el codi SWIFT/BIC de la compta bancària.")
                if not iban_obj.dni:
                    errors.append("Falta el NIF/DNI del titular de la compta bancària.")
                if not iban_obj.name:
                    errors.append("Falta el nom del titular de la compta bancària.")

    return errors