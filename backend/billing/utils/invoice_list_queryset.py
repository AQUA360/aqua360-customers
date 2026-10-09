"""
Optimized queryset for InvoiceViewSet list (InvoiceMinimalSerializer).
"""
from functools import lru_cache

from django.db.models import Prefetch

from billing.models import Invoice, Payment, Reading
from coredata.models import ConfigProject


@lru_cache(maxsize=1)
def invoice_list_config_tokens():
    return {
        'paid': ConfigProject.objects.get(token='invoice_status_paid_token').value,
        'payoff': ConfigProject.objects.get(token='invoice_status_payoff_token').value,
        'budget': ConfigProject.objects.get(token='invoice_type_budget_token').value,
        'invoice': ConfigProject.objects.get(token='invoice_type_invoice_token').value,
        'vulnerable': ConfigProject.objects.get(token='debt_vulnerable_token').value,
    }


def invoice_list_queryset():
    return (
        Invoice.objects.filter(is_active=True)
        .select_related(
            'status',
            'type',
            'origin',
            'exploitation',
            'contract',
            'contract__piggy_bank',
            'contract__debt_management',
            'contract_request',
            'contract_request__person',
            'contract_request__person__piggy_bank',
            'contract_termination',
            'contract_termination__contract',
            'connection_request',
            'connection_request__person',
            'connection_request__person__piggy_bank',
        )
        .prefetch_related(
            Prefetch(
                'payments',
                queryset=Payment.objects.only(
                    'id', 'invoice_id', 'payment_date', 'is_excluded', 'status_id'
                ).order_by('payment_date'),
            ),
            Prefetch(
                'readings',
                queryset=Reading.objects.only(
                    'id', 'reading_date'
                ).order_by('-reading_date'),
            ),
        )
        .order_by('-issue_date', '-created_at', 'status__position')
    )
