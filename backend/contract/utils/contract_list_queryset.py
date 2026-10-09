"""
Queryset base de llista de contractes (mateix que ContractViewSet) per reutilitzar en exportacions i informes.
"""
from decimal import Decimal
from functools import lru_cache

from django.db.models import (
    BooleanField,
    Case,
    Count,
    Exists,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
    DecimalField,
    When,
)
from django.db.models.functions import Coalesce

from contract.models import Contract, ContractDebtView, ContractObservation, ContractTerminationRequest
from coredata.models import ConfigProject
from coredata.utils.fire_usage_utils import get_fire_usage_tokens
from service.models import SupplyCut, SupplyPoint


def annotate_contract_list_debt_amount(queryset):
    # Lookup indexat a vw_contract_debt (precalculat). No es pot fer un FK sobre
    # la mateixa columna 'token' perquè Django duplica la columna en INSERT/UPDATE.
    debt_subquery = ContractDebtView.objects.filter(
        contract_token=OuterRef('token'),
    ).values('debt_amount')[:1]
    return queryset.annotate(
        debt_amount=Coalesce(
            Subquery(
                debt_subquery,
                output_field=DecimalField(max_digits=20, decimal_places=2),
            ),
            Value(Decimal('0')),
            output_field=DecimalField(max_digits=20, decimal_places=2),
        )
    )


def contract_debt_amounts_by_contract_id(contract_ids):
    """Deute per contracte llegit de vw_contract_debt.

    Única definició de deute del llistat, del detall, del filtre has_debt i de les
    exportacions: tots els pagaments de les factures del contracte que no estiguin
    pagats, abonats, anul·lats ni saldats. Hi entren, doncs, els pagaments en estat
    "En compromís" (les factures amb compromís de pagament segueixen sent deute viu
    fins que es liquiden). Els pagaments d'import negatiu (rectificatives i
    liquidacions a favor del client) no hi resten: el deute no pot ser negatiu.
    """
    contract_ids = [contract_id for contract_id in contract_ids if contract_id]
    if not contract_ids:
        return {}

    id_by_token = dict(
        Contract.objects.filter(id__in=contract_ids).values_list('token', 'id')
    )
    if not id_by_token:
        return {}

    rows = ContractDebtView.objects.filter(
        contract_token__in=id_by_token.keys()
    ).values_list('contract_token', 'debt_amount')
    return {
        id_by_token[token]: (debt_amount if debt_amount is not None else Decimal('0'))
        for token, debt_amount in rows
        if token in id_by_token
    }


def filter_contract_queryset_by_debt(queryset, has_debt):
    """Contractes amb (o sense) deute segons vw_contract_debt, com a semi-join per token."""
    tokens_with_debt = ContractDebtView.objects.filter(
        debt_amount__gt=0
    ).values('contract_token')
    if has_debt:
        return queryset.filter(token__in=tokens_with_debt)
    # Un contracte sense token no surt mai a la vista: compta com a "sense deute".
    return queryset.filter(Q(token__isnull=True) | ~Q(token__in=tokens_with_debt))


def annotate_contract_list_expired_invoices(queryset):
    """Optional heavy annotation — only for serializers that expose expired_invoices."""
    expired_token = ConfigProject.objects.get(token='invoice_status_expired_token').value
    return queryset.annotate(
        expired_invoices=Count(
            'invoices',
            filter=Q(invoices__status__token=expired_token),
        ),
    )


@lru_cache(maxsize=1)
def _fire_config_tokens():
    fire_usage_tokens = tuple(get_fire_usage_tokens())
    try:
        fire_connection_token = ConfigProject.objects.get(
            token='fire_connection_use_type_token'
        ).value
    except ConfigProject.DoesNotExist:
        fire_connection_token = 'incendis'
    return fire_usage_tokens, fire_connection_token


def annotate_contract_list_is_fire(queryset):
    """DB-side flag for list; named differently so it does not clash with the @property."""
    fire_usage_tokens, fire_connection_token = _fire_config_tokens()
    fire_supply_point = SupplyPoint.objects.filter(
        contracts=OuterRef('pk'),
        connection__use_type__token=fire_connection_token,
    )
    return queryset.annotate(
        is_fire_annotated=Case(
            When(use_type__token__in=fire_usage_tokens, then=Value(True)),
            When(Exists(fire_supply_point), then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )


@lru_cache(maxsize=1)
def _termination_status_tokens():
    return (
        ConfigProject.objects.get(token='contract_termination_cancelled_token').value,
        ConfigProject.objects.get(token='contract_termination_completed_token').value,
    )


def _base_contract_list_queryset():
    cancelled_token, completed_token = _termination_status_tokens()

    supply_points_qs = SupplyPoint.objects.select_related(
        'connection',
        'connection__use_type',
        'address',
        'address__street',
        'address__street__type',
        'address__street_number',
        'address__street_number__number_type',
        'address__city',
        'address__country',
    )

    return (
        Contract.objects.select_related(
            'supply_point_default',
            'supply_point_default__status',
            'supply_point_default__meter',
            'supply_point_default__address',
            'supply_point_default__address__street',
            'supply_point_default__address__street__type',
            'supply_point_default__address__street_number',
            'supply_point_default__address__street_number__number_type',
            'supply_point_default__address__city',
            'supply_point_default__address__country',
            'use_type',
            'status',
            'owner',
            'tenant',
            'holder',
            'payment',
            'category',
            'client_type',
            'debt_management',
            'user_pinned',
            'person_contact_email',
            'address_contact',
            'address_contact__address',
            'address_contact__address__street',
            'address_contact__address__street__type',
            'address_contact__address__street_number',
            'address_contact__address__street_number__number_type',
            'address_contact__address__city',
            'address_contact__address__country',
        )
        .prefetch_related(
            Prefetch('supply_points', queryset=supply_points_qs),
            Prefetch(
                'supply_point_default__supply_cuts',
                queryset=SupplyCut.objects.select_related('status', 'cause').order_by('-id'),
                to_attr='_prefetched_supply_cuts',
            ),
            'person_contact_sms',
            'contacts',
            'user_checked',
        )
        .annotate(
            active_contract_termination=Exists(
                ContractTerminationRequest.objects.filter(contract=OuterRef('pk')).exclude(
                    status__token__in=[cancelled_token, completed_token]
                )
            ),
        )
        .order_by('-created_at')
    )


def default_contract_list_queryset():
    """Shared queryset for exports / non-list consumers (keeps expired_invoices)."""
    return annotate_contract_list_expired_invoices(_base_contract_list_queryset())


def contract_list_page_queryset():
    """List action: skip expired_invoices Count (kills pagination COUNT) and add page extras."""
    return annotate_contract_list_is_fire(
        _base_contract_list_queryset().prefetch_related(
            'consumption_stats',
            Prefetch(
                'observations',
                queryset=ContractObservation.objects.filter(
                    is_important=True, is_active=True
                ).select_related('user'),
                to_attr='prefetched_important_observations',
            ),
        )
    )
