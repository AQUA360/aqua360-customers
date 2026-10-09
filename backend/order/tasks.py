# order/tasks.py
import uuid
from celery import shared_task
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _
from notification.models import Notification


@shared_task
def create_order_status_notification(order_id, order_token, status_name):
    """
    Celery task to create notification when order status changes to token "2".
    Uses Django translation with configured LANGUAGE_CODE.
    """
    # Activate the configured language for translation in Celery context
    with translation.override(settings.LANGUAGE_CODE):
        notification_save = {
            "token": str(uuid.uuid4()),
            "name": _("Order status updated"),
            "description": _("Order %(token)s has been updated to status: %(status)s")
            % {
                "token": order_token or order_id,
                "status": status_name,
            },
            "module": "order",
            "entity": "orders",
            "object_id": str(order_id),
            "is_active": True,
        }
        Notification.objects.create(**notification_save)
    return {"status": "success", "order_id": order_id}

@shared_task
def create_change_meter_notification(order_id, order_token):
    with translation.override(settings.LANGUAGE_CODE):
        Notification.objects.create(
            token=str(uuid.uuid4()),
            name=_("Change meter applied"),
            description=_("Order %(token)s: meter change has been applied")
            % {"token": order_token or order_id},
            module="order",
            entity="order_report",
            object_id=str(order_id),
            is_active=True,
        )
    return {"status": "success", "order_id": order_id}
