from django.db.models import Q
from django.utils import timezone

from notification.models import CalendarTask

from .base import DashboardCard, register

ITEMS_LIMIT = 8


@register
class TasksTodayCard(DashboardCard):
    """Tasques pendents d'avui i endarrerides de l'usuari (i les de tothom)."""
    key = 'tasks_today'
    default_size = 'md'
    config_schema = [
        {
            'name': 'scope',
            'type': 'select',
            'default': 'visible',
            'options': [{'value': 'visible'}, {'value': 'mine'}],
        },
    ]

    def get_data(self, user, config):
        today = timezone.localdate()
        qs = CalendarTask.objects.filter(is_active=True, task_done=False, set_date__lte=today)
        if config['scope'] == 'mine':
            qs = qs.filter(user=user)
        else:
            qs = qs.filter(Q(user=user) | Q(user__isnull=True))
        items = qs.select_related('order').order_by('set_date', 'time', 'id')[:ITEMS_LIMIT]
        return {
            'today': qs.filter(set_date=today).count(),
            'overdue': qs.filter(set_date__lt=today).count(),
            'items': [
                {
                    'id': t.id,
                    'name': t.name,
                    'color': t.color,
                    'set_date': t.set_date,
                    'time': t.time,
                    'is_overdue': t.set_date < today,
                    'source': t.source,
                    'order_id': t.order_id,
                    'is_recurring': bool(t.recurrence_id),
                }
                for t in items
            ],
        }
