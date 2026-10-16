import datetime

from django.db.models import Count, Sum

from billing.models import Invoice

from .base import PERIOD_OPTION, DashboardCard, config_value, period_range, register


class InvoiceKpiCard(DashboardCard):
    """Base de les cards de facturació: nombre i import de factures en un període."""
    permission = 'view_billing'
    default_size = 'sm'
    config_schema = [PERIOD_OPTION]

    def queryset(self, user, config):
        raise NotImplementedError

    def _totals(self, qs, start, end):
        return qs.filter(issue_date__gte=start, issue_date__lte=end).aggregate(
            count=Count('id'), amount=Sum('total_final'),
        )

    def get_data(self, user, config):
        start, end = period_range(config['period'])
        qs = self.queryset(user, config)
        current = self._totals(qs, start, end)
        # Període anterior equivalent (mes anterior, trimestre anterior...), per comparar.
        prev_start, prev_end = period_range(config['period'], today=start - datetime.timedelta(days=1))
        previous = self._totals(qs, prev_start, prev_end)
        return {
            'date_from': start,
            'date_to': end,
            'count': current['count'],
            'amount': current['amount'] or 0,
            'previous_count': previous['count'],
            'previous_amount': previous['amount'] or 0,
        }

    def _invoices(self):
        return Invoice.objects.filter(
            is_active=True,
            type__token=config_value('invoice_type_invoice_token', 'F'),
        )


@register
class InvoicesIssuedCard(InvoiceKpiCard):
    """Factures emeses (confirmades), sense comptar els abonaments."""
    key = 'invoices_issued'

    def queryset(self, user, config):
        return self._invoices().filter(is_confirmed=True, is_suppressed=False)


@register
class InvoiceCancellationsCard(InvoiceKpiCard):
    """Anul·lacions: abonaments generats en anul·lar factures (import negatiu)."""
    key = 'invoice_cancellations'
    config_schema = [
        PERIOD_OPTION,
        {'name': 'only_mine', 'type': 'boolean', 'default': False},
    ]

    def queryset(self, user, config):
        qs = self._invoices().filter(is_suppressed=True)
        if config.get('only_mine'):
            # Qui anul·la queda a la factura original, que apunta a l'abonament amb return_token.
            tokens = Invoice.objects.filter(suppressed_by=user, return_token__isnull=False).values('return_token')
            qs = qs.filter(token__in=tokens)
        return qs


@register
class RebillingsCard(InvoiceKpiCard):
    """Refacturacions emeses: factures que en substitueixen una altra."""
    key = 'rebillings'

    def queryset(self, user, config):
        return self._invoices().filter(is_confirmed=True, refactored_token__isnull=False).exclude(refactored_token='')
