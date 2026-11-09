from django_filters import rest_framework as filters

from coredata.models import ConfigProject
from ..models import Invoice
from django.db.models import Q
from functools import reduce
from operator import and_

class InvoiceFilter(filters.FilterSet):
    # Tipus "de negoci" de la factura, per poder distingir des del frontend les
    # factures de consum, les altes i les despeses d'impagats. No hi ha cap camp
    # que ho digui: `Invoice.type` només distingeix Pressupost/Factura, i
    # `InvoiceCategory` no s'utilitza. El tipus es deriva de l'origen
    # (`ProductOrigin`), amb els tokens definits per client a ConfigProject.
    INVOICE_KIND_ORIGIN_CONFIG_TOKENS = {
        'consumption': 'origin_reading_token',
        'registration': 'origin_contract_token',
        'connection': 'origin_connection_token',
        'supply': 'origin_supply_token',
        'other': 'origin_other_token',
    }
    INVOICE_KIND_UNPAID_FEE = 'unpaid_fee'

    search = filters.CharFilter(method='filter_search')
    contract = filters.CharFilter(
        field_name='contract__id',
        lookup_expr='exact'
    )
    contract_request = filters.CharFilter(
        field_name='contract_request__id',
        lookup_expr='exact'
    )
    connection_request = filters.CharFilter(
        field_name='connection_request__id',
        lookup_expr='exact'
    )
    is_invoice = filters.BooleanFilter(
        field_name='is_invoice',
        method='filter_is_invoice'
    )
    origin = filters.CharFilter(
        field_name='origin__id',
        lookup_expr='exact'
    )
    billing = filters.CharFilter(
        field_name='billing__id',
        lookup_expr='exact'
    )
    alert = filters.CharFilter(method='filter_alert')
    holder = filters.CharFilter(
        field_name='customer_token_final',
        lookup_expr='exact'
    )
    status = filters.CharFilter(method='filter_status')
    expired = filters.BooleanFilter(
        field_name='is_expired',
        method='filter_expired'
    )
    serie = filters.CharFilter(method='filter_serie')
    payment_bank_final = filters.CharFilter(field_name='payment_bank_final', lookup_expr='exact')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    payment_type_tokens = filters.CharFilter(method='filter_payment_type_tokens')
    payment_type = filters.CharFilter(
        field_name='payment_type__id',
        lookup_expr='exact'
    )
    contract_null = filters.BooleanFilter(method='filter_contract_null')
    left_to_pay = filters.NumberFilter(field_name='left_to_pay', lookup_expr='exact')
    total_final = filters.NumberFilter(field_name='total_final', lookup_expr='exact')
    general_contract = filters.CharFilter(method='filter_general_contract')
    is_general = filters.BooleanFilter(field_name='is_general', lookup_expr='exact')
    start_issue_date = filters.DateFilter(field_name='issue_date', lookup_expr='gte')
    end_issue_date = filters.DateFilter(field_name='issue_date', lookup_expr='lte')
    start_due_date = filters.DateFilter(field_name='due_date', lookup_expr='gte')
    end_due_date = filters.DateFilter(field_name='due_date', lookup_expr='lte')
    start_total_final_range = filters.NumberFilter(field_name='total_final', lookup_expr='gte')
    end_total_final_range = filters.NumberFilter(field_name='total_final', lookup_expr='lte')
    is_excluded = filters.BooleanFilter(field_name='is_excluded', lookup_expr='exact')
    person = filters.CharFilter(field_name='person__id', lookup_expr='exact')
    line_item = filters.CharFilter(method='filter_line_item')
    invoice_kinds = filters.CharFilter(method='filter_invoice_kinds')
    multi_page = filters.BooleanFilter(method='filter_multi_page')
    # Despeses d'impagat (billing/utils/unpaid_fee_service.py)
    unpaid_status = filters.CharFilter(method='filter_unpaid_status')
    without_fee_price_rates = filters.CharFilter(method='filter_without_fee_price_rates')
    exclude_vulnerable = filters.BooleanFilter(method='filter_exclude_vulnerable')
    exclude_terminated = filters.BooleanFilter(method='filter_exclude_terminated')
    exclude_open_claim = filters.BooleanFilter(method='filter_exclude_open_claim')
    
    class Meta:
        model = Invoice
        fields = [
            'search', 'contract', 'contract_request', 'is_invoice',
            'origin', 'connection_request', 'status', 'expired',
            'billing', 'alert', 'holder', 'serie', 'exploitation', 
            'contract_null', 'payment_bank_final', 'left_to_pay',
            'total_final', 
            'general_contract',
            'is_general',
            'payment_type_tokens',
            'payment_type',
            'is_excluded',
            'line_item',
            'person',
            'invoice_kinds',
            'multi_page',
            'unpaid_status',
            'without_fee_price_rates',
            'exclude_vulnerable',
            'exclude_terminated',
            'exclude_open_claim',
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        
        search_terms = value.split()
        term_queries = []
        for term in search_terms:
            term_query = (
                Q(title_final__icontains=term) |
                Q(number__icontains=term) |
                Q(contract__token__icontains=term) |
                Q(contract_request__token__icontains=term) |
                Q(customer_final__icontains=term) |
                Q(customer_token_final__icontains=term) |
                Q(payment_bank_final__icontains=term) |
                Q(address_final__icontains=term) |
                Q(token__icontains=term) |
                Q(serie_final__icontains=term)
            )
            term_queries.append(term_query)
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)
    
    def filter_line_item(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(line_items__product_name__icontains=value) |
            Q(line_items__name__icontains=value) |
            Q(line_items__description__icontains=value)
        ).distinct()
    
    def filter_invoice_kinds(self, queryset, name, value):
        """Filtra per tipus de factura (llista separada per comes).

        Els tipus basats en l'origen s'uneixen en OR. Les despeses d'impagats
        (`invoice_return_charge()`) no tenen un origen propi — neixen amb
        `origin_other_token` — i es reconeixen per tenir una línia amb la
        `PriceRate` del ConfigProject `invoice_return_price_rate_token`, el
        mateix marcador que fa servir `claimrequest/tasks.py` i la generació de
        remeses SEPA. Per això, quan es demana "altres" sense demanar les
        despeses, aquestes es deixen fora: així els tipus no se superposen.
        """
        if not value:
            return queryset

        kinds = {kind.strip() for kind in value.split(',') if kind.strip()}
        if not kinds:
            return queryset

        return_fee_token = ConfigProject.objects.filter(
            token='invoice_return_price_rate_token'
        ).values_list('value', flat=True).first()

        query = Q()
        matched = False

        if self.INVOICE_KIND_UNPAID_FEE in kinds:
            if not return_fee_token:
                # Sense el marcador configurat no es poden identificar: més val
                # no retornar res que retornar-ho tot com si no hi hagués filtre.
                return queryset.none()
            query |= Q(line_items__price_rate__token=return_fee_token)
            matched = True

        origin_config_tokens = [
            self.INVOICE_KIND_ORIGIN_CONFIG_TOKENS[kind]
            for kind in kinds
            if kind in self.INVOICE_KIND_ORIGIN_CONFIG_TOKENS
        ]
        if origin_config_tokens:
            origin_tokens = list(
                ConfigProject.objects.filter(
                    token__in=origin_config_tokens
                ).values_list('value', flat=True)
            )
            if origin_tokens:
                origin_query = Q(origin__token__in=origin_tokens)
                if return_fee_token and self.INVOICE_KIND_UNPAID_FEE not in kinds:
                    origin_query &= ~Q(
                        id__in=Invoice.objects.filter(
                            line_items__price_rate__token=return_fee_token
                        ).values('id')
                    )
                query |= origin_query
                matched = True

        if not matched:
            return queryset
        return queryset.filter(query).distinct()

    def filter_payment_type_tokens(self, queryset, name, value):
        if value:
            payment_type_tokens = value.split(',')
            return queryset.filter(payment_type_token_final__in=payment_type_tokens)
        return queryset
    
    def filter_general_contract(self, queryset, name, value):
        if value:
            return queryset.filter(general_contracts__id=value).distinct()
        return queryset
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_expired(self, queryset, name, value):
        if value is True:
            status_expired = ConfigProject.objects.get(
                token='invoice_status_expired_token'
            ).value
            return queryset.filter(status__token=status_expired)
        return queryset
    
    def filter_is_invoice(self, queryset, name, value):
        if value is True:
            return queryset.filter(
                type__token=ConfigProject.objects.get(
                    token='invoice_type_invoice_token'
                ).value
            )
        elif value is False:
            return queryset.filter(
                type__token=ConfigProject.objects.get(
                    token='invoice_type_budget_token'
                ).value
            )
        return queryset
    
    def filter_alert(self, queryset, name, value):
        if value == 'any':
            return queryset.filter(warning__isnull=False)
        elif value == 'null':
            return queryset.filter(warning__isnull=True)
        elif value == 'high_billing_amount':
            try:
                high_amount_token = ConfigProject.objects.get(token='invoice_warning_high_amount').value
                return queryset.filter(warning__token=high_amount_token)
            except ConfigProject.DoesNotExist:
                return queryset.none()
        elif value == 'warning_date_range':
            return queryset
        else:
            return queryset.filter(warning__name=value)
        
    def filter_serie(self, queryset, name, value):
        if value:
            values = value.split(',')
            return queryset.filter(serie__id__in=values)
        return queryset
    
    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(exploitation__id=value) |
                Q(exploitation__isnull=True)
                )
        return queryset
    
    def filter_multi_page(self, queryset, name, value):
        # Factures el PDF de les quals ocupa més d'una pàgina (o, amb false, la resta).
        if value is True:
            return queryset.filter(pdf_page_count__gt=1)
        if value is False:
            return queryset.exclude(pdf_page_count__gt=1)
        return queryset

    def filter_contract_null(self, queryset, name, value):
        if value is True:
            return queryset.filter(contract__isnull=True, contract_request__isnull=True, contract_termination__isnull=True)
        return queryset

    # Els filtres de sota fan servir subconsultes d'ids: amb joins directes per
    # `payments` o `child_invoices` la llista sortiria amb factures repetides.

    def filter_unpaid_status(self, queryset, name, value):
        """Factures pendents de cobrar: `expired` (vençudes) i/o `returned` (rebut retornat)."""
        from billing.utils.unpaid_fee_service import unpaid_status_q
        kinds = {kind.strip() for kind in (value or '').split(',') if kind.strip()}
        if not kinds:
            return queryset
        query = unpaid_status_q(kinds)
        if not query:
            return queryset.none()
        return queryset.filter(
            id__in=Invoice.objects.filter(query).values('id'),
            left_to_pay__gt=0,
        )

    def filter_without_fee_price_rates(self, queryset, name, value):
        """Treu les factures de despeses d'aquestes tarifes i les que ja en tenen."""
        from billing.utils.unpaid_fee_service import with_fee_ids
        price_rate_ids = [v.strip() for v in (value or '').split(',') if v.strip().isdigit()]
        if not price_rate_ids:
            return queryset
        return queryset.exclude(id__in=with_fee_ids(price_rate_ids))

    def filter_exclude_vulnerable(self, queryset, name, value):
        from billing.utils.unpaid_fee_service import vulnerable_q
        if value is not True:
            return queryset
        return queryset.exclude(id__in=Invoice.objects.filter(vulnerable_q()).values('id'))

    def filter_exclude_terminated(self, queryset, name, value):
        from billing.utils.unpaid_fee_service import terminated_contract_q
        query = terminated_contract_q() if value is True else None
        if not query:
            return queryset
        return queryset.exclude(id__in=Invoice.objects.filter(query).values('id'))

    def filter_exclude_open_claim(self, queryset, name, value):
        from billing.utils.unpaid_fee_service import open_claim_q
        query = open_claim_q() if value is True else None
        if not query:
            return queryset
        return queryset.exclude(id__in=Invoice.objects.filter(query).values('id'))
