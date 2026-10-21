import datetime
import json
import logging
import re
from order.models import Operator, Order, OrderStatus, OrderObservation
from django.db.models import Q
from django.utils import timezone
from coredata.models import Address, ConfigProject

logger = logging.getLogger(__name__)

# Status mapping constants
GMAO_STATUS_MAPPING_CONFIG = ConfigProject.objects.filter(token="gmao_integration_order_status_mapping").first()
if not GMAO_STATUS_MAPPING_CONFIG:
    logger.warning("GMAO_STATUS_MAPPING config not found, using default mapping")
    GMAO_STATUS_MAPPING = {
        "pending": "1",
        "in_progress": "5",
        "completed": "5",
        "finalized": "2",
        "cancelled": "-1",
    }
else:
    try:
        GMAO_STATUS_MAPPING = json.loads(GMAO_STATUS_MAPPING_CONFIG.value)
        logger.info(f"Loaded GMAO_STATUS_MAPPING from config: {GMAO_STATUS_MAPPING}")
    except Exception as e:
        logger.error(f"Error parsing GMAO_STATUS_MAPPING config: {e}")
        GMAO_STATUS_MAPPING = {
            "pending": "1",
            "in_progress": "5",
            "completed": "5",
            "finalized": "2",
            "cancelled": "-1",
        }

# Visual flags for orders created in GMAO that cannot be linked to any entity
MANUAL_REVIEW_FLAG = "[REVISIÓ MANUAL]"
ORPHAN_ORDER_NOTE = (
    "ATENCIÓ: Ordre òrfena pendent de vincular a un Punt de Subministrament o Contracte. "
    "Adreça proporcionada pel GMAO: {address}"
)

def process_message(payload: dict) -> dict:
    """
    Process incoming RabbitMQ message and route to appropriate handler.
    """
    if not isinstance(payload, dict):
        logger.error(f"process_message: payload must be a dict, got {type(payload)}")
        raise ValueError("payload must be a dict")

    key = payload.get("key")

    if not key:
        logger.error(f"process_message: message missing 'key' field")
        raise ValueError("missing 'key' field")

    if key == "order.status.changed":
        return handle_order_status_change(payload)
    elif key == "order.created":
        return handle_order_created(payload)
    elif key == "observation.created":
        return handle_observation_created(payload)
    else:
        logger.error(f"process_message: unknown key '{key}'")
        raise ValueError(f"unknown key: {key}")


def handle_order_status_change(payload: dict) -> dict:
    """
        Handle order status change from GMAO.
        Updates order status and processes attached files and form responses.

        Payload structure:
        {
            "key": "order.status.changed",
            "order_token": "O2026020001",
            "status_id": 5,
            "status_token": "GM-f37920260204084533",
            "status_name": "Cancel·lat",
            "reports": [
                {
                "start_at": "2026-02-09T11:10:41.638000+00:00",
                "end_at": "2026-02-09T13:10:00+00:00",
                "description": "Shehshehe",
                "username": "operator1",
                "user_first_name": "John",
                "user_last_name": "Doe",
                "photos": [
                "/media/task_reports/photos/photo_h9exJHf.jpg",
                "/media/task_reports/photos/photo_h9exJHf.jpg"
                ],
                "form_submission": [
                    {
                        "token": "pressio",
                        "response": "55"
                    },
                    {
                        "token": "foto",
                        "response": "/media/task_reports/photos/photo_h9exJHf.jpg"
                    }
                ]
        }
      ]
    }
    """
    try:
        # Extract required fields
        order_token = payload.get("order_token")
        status = payload.get("status_token")

        # Validate required fields
        if not order_token:
            logger.error("handle_order_status_change: missing order_token")
            raise ValueError("missing order_token")

        if not status:
            logger.error("handle_order_status_change: missing status")
            raise ValueError("missing status")

        # Find the order by token
        try:
            order = Order.objects.get(token=order_token)
        except Order.DoesNotExist:
            logger.error(
                f"handle_order_status_change: Order with token '{order_token}' not found"
            )
            raise ValueError(f"Order '{order_token}' not found")

        # Get the mapped status token
        status_token = GMAO_STATUS_MAPPING.get(status)

        if status_token is None:
            logger.warning(
                f"handle_order_status_change: Unknown status '{status}', skipping status update"
            )
        else:
            # Get the OrderStatus object
            try:
                order_status = OrderStatus.objects.get(token=status_token)
                old_status = order.status.name if order.status else "None"
                order.status = order_status

                # If status is closed (token=2), set completed_at
                if status_token == 2:
                    order.completed_at = timezone.now()

                order.save()
                logger.info(
                    f"handle_order_status_change: Updated order '{order_token}' status from '{old_status}' to '{order_status.name}' (token={status_token})"
                )
            except OrderStatus.DoesNotExist:
                logger.error(
                    f"handle_order_status_change: OrderStatus with token '{status_token}' not found"
                )
                raise ValueError(f"OrderStatus token '{status_token}' not found")

        # Process order report with files and form responses
        from order.services.handle_order_report import process_gmao_order_report

        reports = payload.get("reports", [])
        report_results = process_gmao_order_report(order, reports)

        result = {
            "success": True,
            "order_token": order_token,
            "status_updated": status_token is not None,
            "new_status_token": status_token,
            "reports_processed": len(report_results),
            "report_ids": report_results,
        }

        logger.info(f"handle_order_status_change: Completed - {result}")
        return result

    except Exception as e:
        logger.error(
            f"handle_order_status_change: Unexpected error - {e}", exc_info=True
        )
        raise ValueError(f"Unexpected error: {e}")


# Street name normalization for address matching. The shared
# service.utils.property_route_service.clean_street_name_for_search helper is
# not usable here: its alternation matches the bare "C" of "Carrer" first and
# mangles full names ("Carrer Major" -> "arrer Major").
_STREET_PREFIX_PATTERN = re.compile(
    r"^\s*(?:CARRER|AVINGUDA|PASSEIG|PLAÇA|PLAZA|RAMBLA|RBLA|CARRETERA|CAMÍ|CAMI|AVENIDA|CALLE|AV|PL|PG|PS|C)\b[\s./]*",
    re.IGNORECASE,
)
_STREET_PREPOSITION_PATTERN = re.compile(
    r"^(?:D'\s*|DE\s+LA\s+|DE\s+LES\s+|DE\s+ELS\s+|DEL\s+|DE\s+)",
    re.IGNORECASE,
)


def _normalize_street_name(name: str) -> str:
    if not name:
        return name
    cleaned = _STREET_PREFIX_PATTERN.sub("", name.strip(), count=1).strip()
    cleaned = _STREET_PREPOSITION_PATTERN.sub("", cleaned, count=1).strip()
    return cleaned


def _parse_address_text(raw_address: str) -> dict:
    """
    Extract structured components from a free-text address sent by GMAO.

    Returns a dict with street_name, number, postal_code and city_name
    (None for the components that cannot be derived).
    """
    from service.utils.property_route_service import extract_integer_from_street_number

    parsed = {
        "street_name": None,
        "number": None,
        "postal_code": None,
        "city_name": None,
    }
    if not raw_address:
        return parsed

    text = raw_address.strip()

    postal_match = re.search(r"\b(\d{5})\b", text)
    if postal_match:
        parsed["postal_code"] = postal_match.group(1)

    segments = [segment.strip() for segment in text.split(",") if segment.strip()]
    street_segment = segments[0] if segments else text
    if postal_match and postal_match.group(1) in street_segment:
        street_segment = street_segment.replace(postal_match.group(1), "").strip(" ,")

    tokens = street_segment.split()
    if tokens and re.fullmatch(r"\d+\s*[A-Za-z-]*", tokens[-1]):
        parsed["number"] = extract_integer_from_street_number(tokens[-1])
        street_raw = " ".join(tokens[:-1])
    else:
        street_raw = street_segment

    street_name = _normalize_street_name(street_raw)
    if street_name:
        parsed["street_name"] = street_name

    # Number written after the comma (e.g. "C. Major, 75"): first numeric
    # segment that is not the postal code
    if parsed["number"] is None:
        for segment in segments[1:]:
            if postal_match and postal_match.group(1) in segment:
                continue
            candidate = segment.split()[0] if segment.split() else ""
            if re.fullmatch(r"\d+\s*[A-Za-z-]*", candidate):
                parsed["number"] = extract_integer_from_street_number(candidate)
                break

    if postal_match:
        after_postal = text[postal_match.end():].split(",", 1)[0].strip()
        if after_postal:
            parsed["city_name"] = after_postal

    return parsed


def _resolve_supply_point_by_address(raw_address: str):
    """
    Resolve SupplyPoint/Address/Contract from the GMAO free-text address.

    Returns (supply_point, address, contract):
    - supply_point: set only when exactly ONE active supply point matches
      (active = is_active and status token != the configured "baixa" token;
      a NULL status counts as active).
    - address: set when exactly ONE Address row matches, even if the supply
      point is ambiguous or missing, so the orphan order still displays the
      address in the grid; with several matching addresses, the resolved
      supply point's address is used when available.
    - contract: only when the supply point resolved and exactly one active
      contract defaults to it.
    Never raises: the caller falls back to an orphan order for manual review.
    """
    from service.models import SupplyPoint

    parsed = _parse_address_text(raw_address)

    if not parsed["street_name"]:
        logger.warning(
            f"_resolve_supply_point_by_address: cannot derive a street name from '{raw_address}', skipping address matching"
        )
        return None, None, None

    filters = Q(street__name__icontains=parsed["street_name"])
    if parsed["number"] is not None:
        filters &= Q(street_number__number=parsed["number"])
    if parsed["postal_code"]:
        filters &= Q(postal_code__icontains=parsed["postal_code"])
    if parsed["city_name"]:
        city = parsed["city_name"]
        filters &= Q(city__name__icontains=city) | Q(city_name__icontains=city)

    addresses = list(Address.objects.filter(filters).distinct()[:2])
    if not addresses:
        logger.warning(
            f"_resolve_supply_point_by_address: '{raw_address}' matched 0 addresses, skipping address matching"
        )
        return None, None, None

    # Loose active filter: exclude only deactivated ("baixa") statuses,
    # NULL status rows remain eligible
    deactivate_config = ConfigProject.objects.filter(
        token="supply_point_status_deactivate_token"
    ).first()
    deactivate_token = deactivate_config.value if deactivate_config else "-1"

    supply_points = list(
        SupplyPoint.objects.filter(address__in=addresses, is_active=True)
        .filter(
            Q(status__isnull=True)
            | Q(status__token__isnull=True)
            | ~Q(status__token=deactivate_token)
        )
        .distinct()[:2]
    )

    supply_point = supply_points[0] if len(supply_points) == 1 else None
    if len(supply_points) != 1:
        logger.warning(
            f"_resolve_supply_point_by_address: '{raw_address}' matched {len(addresses)} addresses and "
            f"{len(supply_points)} active supply points (0 or ambiguous)"
        )

    contract = None
    if supply_point is not None:
        contracts = list(supply_point.default_contracts.filter(is_active=True)[:2])
        if len(contracts) == 1:
            contract = contracts[0]
        elif len(contracts) > 1:
            logger.warning(
                f"_resolve_supply_point_by_address: supply point '{supply_point.token}' has {len(contracts)} active contracts, leaving contract unset"
            )

    if len(addresses) == 1:
        address = addresses[0]
    elif supply_point is not None:
        address = supply_point.address
    else:
        address = None

    return supply_point, address, contract


def _build_order_description(title, body, raw_address, orphan: bool) -> str:
    title = (title or "").strip()
    body = (body or "").strip()
    raw_address = (raw_address or "").strip()

    if orphan:
        flagged_title = (
            f"{MANUAL_REVIEW_FLAG} {title}" if title else MANUAL_REVIEW_FLAG
        )
        note = ORPHAN_ORDER_NOTE.format(address=raw_address or "cap")
        parts = [f"{flagged_title}\n{note}"]
        if body:
            parts.append(body)
        return "\n\n".join(parts)

    parts = []
    if title:
        parts.append(title)
    if body:
        parts.append(body)
    if raw_address:
        parts.append(f"Adreça GMAO: {raw_address}")
    return "\n\n".join(parts)


def _get_or_create_gmao_user():
    """
    System user attributed to orders created directly in GMAO
    (Order.created_by). Unusable password and no privileges: it exists
    only for attribution, it cannot log in.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user, created = User.objects.get_or_create(
        username="GMAO",
        defaults={"is_staff": False, "is_superuser": False},
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
        logger.info("_get_or_create_gmao_user: created system user 'GMAO'")
    return user


def handle_order_created(payload: dict) -> dict:
    """
        Handle new order created directly in GMAO, synced back to the CRM.

        Linking resolution (in order, never raises on failure):
        1. Parent Order: link and inherit contract/supply_point/type/reason/
           priority/address from parent_order_token.
        2. Address: match the free-text address against structured Address
           fields -> unique SupplyPoint. A unique Address alone still links
           the address; the order stays orphan until a unique supply point
           exists.
        3. Orphan: create the Order without supply point/contract and flag
           the description for manual review (no ValueError, no DLQ).
        The order is always attributed to the 'GMAO' system user.

        Payload structure:
        {
            "key": "order.created",
            "order_token": "O-GMAO-202610-001",
            "order_title": "Reparació extra de fuita",
            "order_description": "Detectada fuita secundària durant la inspecció.",
            "scheduled_at": "2026-10-19T14:00:00Z",
            "due_date": "2026-10-20T14:00:00Z",
            "parent_order_token": "O2026020001",
            "address": "Carrer Major 12, 08500 Vic",
            "status_id": 1,
            "status_token": "GM-init",
            "status_name": "Pendent",
            "reports": []
        }
    """
    try:
        order_token = payload.get("order_token")

        if not order_token:
            logger.error("handle_order_created: missing order_token")
            raise ValueError("missing order_token")

        # Idempotency: GMAO may redeliver the same event
        if Order.objects.filter(token=order_token).exists():
            logger.info(
                f"handle_order_created: Order '{order_token}' already exists, skipping (idempotent)"
            )
            return {
                "success": True,
                "created": False,
                "idempotent": True,
                "order_token": order_token,
            }

        raw_address = (payload.get("address") or "").strip()
        parent_token = payload.get("parent_order_token")

        parent = None
        if parent_token:
            parent = Order.objects.filter(token=parent_token).first()
            if parent is None:
                logger.warning(
                    f"handle_order_created: parent order '{parent_token}' not found, falling back to address matching"
                )

        supply_point = contract = address = None
        type_instance = reason = priority = None

        if parent is not None:
            linking_tier = "parent"
            contract = parent.contract
            supply_point = parent.supply_point
            address = parent.address
            type_instance = parent.type
            reason = parent.reason
            priority = parent.priority
        else:
            supply_point, address, contract = _resolve_supply_point_by_address(raw_address)
            if supply_point is not None:
                linking_tier = "address"
            else:
                linking_tier = "orphan"

        orphan = linking_tier == "orphan"

        # Status: map GMAO status token, fallback to the default CRM status
        status_token = payload.get("status_token")
        mapped_status_token = GMAO_STATUS_MAPPING.get(status_token) if status_token else None
        if mapped_status_token is not None:
            try:
                status = OrderStatus.objects.get(token=mapped_status_token)
            except OrderStatus.DoesNotExist:
                logger.error(
                    f"handle_order_created: OrderStatus with token '{mapped_status_token}' not found"
                )
                raise ValueError(f"OrderStatus token '{mapped_status_token}' not found")
        else:
            if status_token:
                logger.warning(
                    f"handle_order_created: Unknown status '{status_token}', using default status"
                )
            status = OrderStatus.objects.filter(is_default=True).first()
            if status is None:
                logger.error("handle_order_created: no default OrderStatus configured")
                raise ValueError("default OrderStatus not found")

        # due_date -> dueDateAt (DateField)
        due_date = None
        raw_due_date = payload.get("due_date")
        if raw_due_date:
            try:
                due_date = datetime.datetime.fromisoformat(
                    str(raw_due_date).replace("Z", "+00:00")
                ).date()
            except (ValueError, TypeError):
                logger.warning(
                    f"handle_order_created: invalid due_date '{raw_due_date}', ignoring"
                )

        scheduled_at = payload.get("scheduled_at")
        if scheduled_at:
            logger.info(
                f"handle_order_created: scheduled_at '{scheduled_at}' ignored (no equivalent CRM field)"
            )

        description = _build_order_description(
            title=payload.get("order_title"),
            body=payload.get("order_description"),
            raw_address=raw_address,
            orphan=orphan,
        )

        order = Order(
            token=order_token,
            contract=contract,
            supply_point=supply_point,
            address=address,
            type=type_instance,
            reason=reason,
            priority=priority,
            status=status,
            dueDateAt=due_date,
            description=description,
            created_by=_get_or_create_gmao_user(),
        )
        # Do not echo the creation back to GMAO (order originates there)
        order._skip_publish = True
        order.save()

        if orphan:
            logger.warning(
                f"handle_order_created: created ORPHAN order '{order_token}' without supply point/contract links (manual review required)"
            )

        # Reuse the existing GMAO report parser (files, form submissions)
        from order.services.handle_order_report import process_gmao_order_report

        reports = payload.get("reports", [])
        report_results = process_gmao_order_report(order, reports)

        result = {
            "success": True,
            "created": True,
            "order_token": order_token,
            "linking_tier": linking_tier,
            "parent_order_token": parent_token,
            "supply_point_token": supply_point.token if supply_point else None,
            "contract_token": contract.token if contract else None,
            "status_token": status.token if status else None,
            "reports_processed": len(report_results),
            "report_ids": report_results,
        }

        logger.info(f"handle_order_created: Completed - {result}")
        return result

    except Exception as e:
        logger.error(
            f"handle_order_created: Unexpected error - {e}", exc_info=True
        )
        raise ValueError(f"Unexpected error: {e}")


def handle_observation_created(payload: dict) -> dict:
    """
    Handle new order observation from GMAO.

    Payload structure:
    {
        "key": "observation.created",
        "order_token": "260210/SP9/CM137",
        "message": "HOLA ARSHAN",
        "created_at": "2026-02-12T11:13:31.129362+00:00",
        "username": "admin",
        "user_first_name": "Admin",
        "user_last_name": "Aventec"
    }
    """
    try:
        order_token = payload.get("order_token")
        username = payload.get("username")
        message = payload.get("message")

        if not order_token or not username or not message:
            logger.error("handle_observation_created: missing required fields")
            raise ValueError("missing required fields (order_token, username, message)")

        try:
            order = Order.objects.get(token=order_token)
        except Order.DoesNotExist:
            logger.error(
                f"handle_observation_created: Order with token '{order_token}' not found"
            )
            raise ValueError(f"Order '{order_token}' not found")

        # Get or create Operator with GMAO_ prefix
        operator_token = f"GMAO_{username}"
        operator, created = Operator.objects.get_or_create(
            token=operator_token,
            defaults={
                "name": payload.get("user_first_name", ""),
                "surname": payload.get("user_last_name", ""),
                "is_active": True,
            },
        )

        if created:
            logger.info(f"Created new operator from GMAO observation: {operator_token}")

        # Create OrderObservation
        observation = OrderObservation(
            order=order,
            operator=operator,
            observation=message,
        )
        observation._skip_signal = True
        observation.save()

        result = {
            "success": True,
            "order_token": order_token,
            "observation_id": observation.id,
            "operator_token": operator_token,
        }

        logger.info(f"handle_observation_created: Completed - {result}")
        return result

    except Exception as e:
        logger.error(
            f"handle_observation_created: Unexpected error - {e}", exc_info=True
        )
        raise ValueError(f"Unexpected error: {e}")
