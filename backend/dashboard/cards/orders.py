from order.models import Order, OrderStatus

from .base import DashboardCard, config_value, register

ITEMS_LIMIT = 5


def _order_item(order):
    return {
        'id': order.id,
        'token': order.token,
        'type': order.type.name if order.type else None,
        'created_at': order.created_at,
        'created_by': order.created_by.username if order.created_by else None,
    }


@register
class OrdersToValidateCard(DashboardCard):
    """OT que han arribat a l'estat «per validar»."""
    key = 'orders_to_validate'
    permission = 'view_order'
    default_size = 'md'
    config_schema = [
        {
            'name': 'scope',
            'type': 'select',
            'default': 'all',
            'options': [{'value': 'all'}, {'value': 'created_by_me'}],
        },
    ]

    def get_data(self, user, config):
        token = config_value('for_validate_order_status_token', '2')
        status = OrderStatus.objects.filter(token=token).first()
        qs = Order.objects.filter(is_active=True, status__token=token)
        if config['scope'] == 'created_by_me':
            qs = qs.filter(created_by=user)
        items = qs.select_related('type', 'created_by').order_by('-updated_at')[:ITEMS_LIMIT]
        return {
            'count': qs.count(),
            'status_id': status.id if status else None,
            'items': [_order_item(o) for o in items],
        }


@register
class ChangeMeterPendingCard(DashboardCard):
    """OT de canvi de comptador tancades sense haver aplicat el canvi al sistema."""
    key = 'change_meter_pending'
    permission = 'view_order'
    default_size = 'md'

    def get_data(self, user, config):
        from notification.utils.auto_tasks import change_meter_order_types

        completed_token = config_value('order_status_completed_token', '10')
        qs = Order.objects.filter(
            is_active=True,
            status__token=completed_token,
            type__token__in=change_meter_order_types(),
            change_meter_applied_at__isnull=True,
        )
        items = qs.select_related('type', 'created_by').order_by('-completed_at')[:ITEMS_LIMIT]
        return {
            'count': qs.count(),
            'items': [_order_item(o) for o in items],
        }
