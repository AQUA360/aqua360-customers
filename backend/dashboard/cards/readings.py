from django.db.models import Count, Q

from billing.models import Reading, ReadingBatch

from .base import DashboardCard, config_value, register

ITEMS_LIMIT = 5


@register
class ReadingBatchesInProgressCard(DashboardCard):
    """Lots de lectures no facturats ni cancel·lats, amb l'estat de les seves lectures."""
    key = 'reading_batches_in_progress'
    permission = 'view_reading'
    default_size = 'lg'

    def get_data(self, user, config):
        """Return active reading batches with reading counts, alerts and progress."""
        tokens = [
            config_value('reading_batch_pending_token', '1'),
            config_value('reading_batch_pending_processing_token', '4'),
            config_value('reading_batch_processing_token', '5'),
            config_value('reading_batch_billing_pending_token', '2'),
        ]
        qs = ReadingBatch.objects.filter(is_active=True, is_excluded=False, status__token__in=tokens)
        batches = list(qs.select_related('status').order_by('-created_at')[:ITEMS_LIMIT])

        stats = {
            row['batch_id']: row
            for row in Reading.objects.filter(batch_id__in=[b.id for b in batches])
            .values('batch_id')
            .annotate(
                total=Count('id', filter=Q(is_control=False)),
                read=Count('id', filter=Q(is_control=False, reading_value__isnull=False)),
                alerts=Count('id', filter=Q(alert__isnull=False)),
            )
        }

        items = []
        for batch in batches:
            row = stats.get(batch.id, {})
            total = row.get('total', 0)
            read = row.get('read', 0)
            items.append({
                'id': batch.id,
                'name': batch.name or batch.token,
                'created_at': batch.created_at,
                'status': {
                    'token': batch.status.token,
                    'name': batch.status.name,
                    'color': batch.status.color,
                } if batch.status else None,
                'last_task_status': batch.last_task_status,
                'readings_total': total,
                'readings_read': read,
                'readings_alerts': row.get('alerts', 0),
                'progress': round(100 * read / total) if total else 0,
            })
        return {'count': qs.count(), 'items': items}
