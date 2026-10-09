import json
import logging
from order.models import Operator, Order, OrderStatus, OrderObservation
from django.utils import timezone
from coredata.models import ConfigProject

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
