from django_filters import rest_framework as filters
from contract.models import Contract
from coredata.models import ConfigProject
from service.models import SupplyPoint
from django.db.models import Q, Count, F , Value , Case, When, IntegerField
from django.db.models.functions import Concat, Replace
from django.db import models
from functools import reduce
from operator import and_
from urllib.parse import unquote
import re


class ContractFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    search_all_address = filters.CharFilter(method='filter_all_address')
    search_by_address = filters.CharFilter(method='filter_address')
    search_email = filters.CharFilter(method='filter_email')
    search_iban = filters.CharFilter(method='filter_iban')
    search_meter = filters.CharFilter(method='filter_meter')
    search_by_token = filters.CharFilter(method='search_token')
    #
    token= filters.CharFilter(method='filter_token')
    status = filters.CharFilter(method='filter_status')
    category = filters.CharFilter(method='filter_category')
    company = filters.CharFilter(method='filter_company')
    client_type = filters.CharFilter(method='filter_client_type')
    use_type = filters.CharFilter(method='filter_use_type')
    holder = filters.CharFilter(method='filter_holder')
    supply_point = filters.CharFilter(method='filter_supply_point')
    debt_management = filters.CharFilter(method='filter_debt_management')
    communication_type = filters.CharFilter(method='filter_communication_type')
    payment_type = filters.CharFilter(method='filter_payment_type')
    exploitation = filters.NumberFilter(field_name='supply_point_default__connection__exploitation__id', lookup_expr='exact')
    
    variable_type = filters.CharFilter(method='filter_variable_type')
    bonification_type = filters.CharFilter(method='filter_bonification_type')
    product = filters.CharFilter(method='filter_product')
    
    persons = filters.CharFilter(method='filter_persons')
    
    expired = filters.BooleanFilter(method='filter_expired')
    zone = filters.CharFilter(method='filter_zone')
    #start_at = filters.DateTimeFilter(field_name='invoice__issue_date', lookup_expr='gte')
    #end_at = filters.DateTimeFilter(field_name='invoice__issue_date', lookup_expr='lte')
    start_at = filters.DateTimeFilter(method='filter_start_at')
    end_at = filters.DateTimeFilter(method='filter_end_at')
    
    is_pinned = filters.BooleanFilter(method='filter_is_pinned')
    is_checked = filters.BooleanFilter(method='filter_is_checked')
    is_active = filters.BooleanFilter(field_name='is_active')
    role = filters.CharFilter(method='no_op')
    total_persons_min = filters.NumberFilter(field_name='total_persons', lookup_expr='gte')
    block_billing = filters.CharFilter(method='filter_block_billing')
    has_debt = filters.CharFilter(method='filter_has_debt')
    
    class Meta:
        model = Contract
        fields = ['search','search_by_token', 'status', 'category', 
                  'client_type', 'use_type', 'variable_type', 
                  'bonification_type', 'supply_point', 'holder', 
                  'expired', 'debt_management', 'zone', 
                  'start_at', 'end_at', 'product', 
                  'is_pinned', 'is_checked', 'is_active', 'exploitation',
                  'communication_type', 'payment_type', 'persons', 'role', 'total_persons_min', 'block_billing',
                  'has_debt']

    def filter_queryset(self, queryset):
        queryset = queryset.filter(is_active=True)
        return super().filter_queryset(queryset)
        
    def filter_payment_type(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            include_null = "null" in value_ids  
            
            value_ids = [v for v in value_ids if v != "null"]

            query = Q()
            if value_ids:
                query |= Q(payment__type__id__in=value_ids)
            if include_null:
                query |= Q(payment__isnull=True) | Q(payment__type__isnull=True)
            return queryset.filter(query)
        return queryset
    
    def filter_block_billing(self, queryset, name, value):
        if value is not None:
            is_blocked = value.lower() == 'true'
            return queryset.filter(block_billing=is_blocked)
        return queryset

    def filter_has_debt(self, queryset, name, value):
        if value is None or value == '':
            return queryset

        from contract.utils.contract_list_queryset import filter_contract_queryset_by_debt

        normalized = str(value).lower()
        if normalized in ("true", "1"):
            return filter_contract_queryset_by_debt(queryset, True)
        if normalized in ("false", "0"):
            return filter_contract_queryset_by_debt(queryset, False)
        return queryset
    
    def search_token(self, queryset, name, value):
        if value:
            return queryset.filter(token__icontains=value)
        return queryset
    
    def filter_token(self, queryset, name, value):
        if value:
            return queryset.filter(token=value)
        return queryset
    
    def filter_is_pinned(self, queryset, name, value):
        if value:
            return queryset.filter(user_pinned__isnull=False)
        return queryset
    
    def filter_is_checked(self, queryset, name, value):
        if value:
            return queryset.filter(user_checked__isnull=False)
        return queryset
    
    def filter_communication_type(self, queryset, name, value):
        if value:
            comm_values = value.split(',')
            return queryset.filter(communication_type__in=comm_values)
        return queryset
    
    def filter_start_at(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(invoice__issue_date__gte=value) | 
                Q(invoice__payments__payment_date__gte=value)
            ).distinct()
        return queryset

    def filter_end_at(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(invoice__issue_date__lte=value) | 
                Q(invoice__payments__payment_date__lte=value)
            ).distinct()
        return queryset
    
    def filter_use_type(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(use_type__id__in=value_ids)
        return queryset
    
    def filter_client_type(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(client_type__id__in=value_ids)
        return queryset
    
    def filter_category(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(category__id__in=value_ids)
        return queryset
    
    def filter_company(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(company__id__in=value_ids)
        return queryset
    
    def filter_product(self, queryset, name, value):
        print("CONTRACT FILTER PRODUCT")
        if value:
            value_ids = value.split(',')
            q = queryset.annotate(
                matching_products=Count('price_rates__price_rate__product', distinct=True, filter=models.Q(price_rates__price_rate__product__id__in=value_ids))
            ).filter(matching_products=len(value_ids))
            return q
        return queryset
    

    def filter_debt_management(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            include_null = "null" in value_ids  
            
            value_ids = [v for v in value_ids if v != "null"]

            query = Q()
            if value_ids:
                query |= Q(debt_management__id__in=value_ids)
            if include_null:
                query |= Q(debt_management__isnull=True)

            return queryset.filter(query)

        return queryset

    def filter_zone(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(supply_point_default__property__route_position__route__route_zone__id__in=value_ids)
        return queryset
    
    def filter_holder(self, queryset, name, value):
        if not value or value == 'all':
            return queryset
        return queryset.filter(holder__name=value)
    
    def filter_supply_point(self, queryset, name, value):
        return queryset.filter(supply_point_default__id=value)
    
    def filter_expired(self, queryset, name, value):
        if value is True:
            status_expired = ConfigProject.objects.get(token="invoice_status_expired_token").value
            return queryset.filter(invoice__status__token=status_expired).distinct()
        return queryset
    
    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        
        # Split by space so "name surname" matches name + surname across fields
        terms = value.split()
        if not terms:
            return queryset

        # Each term must match at least one searchable field; all terms required
        q_objects = []
        for term in terms:
            term_q = (
                Q(token__icontains=term) |
                Q(holder__name__icontains=term) |
                Q(holder__surname__icontains=term) |
                Q(holder__token__icontains=term) |
                Q(supply_point_default__address__address_search__icontains=term)
            )
            q_objects.append(term_q)

        return queryset.filter(*q_objects).distinct()

    def filter_all_address(self, queryset, name, value):
        if not value:
            return queryset

        # Desencodar valors URL (ex: "maj%204" → "maj 4")
        value = unquote(value)

        # Dividir en paraules
        terms = [t.strip() for t in value.split() if t.strip()]
        if not terms:
            return queryset

        # Construir un filtre AND: totes les paraules han d'aparèixer
        for term in terms:
            queryset = queryset.filter(
                supply_point_default__address__address_search__icontains=term
            )

        return queryset    
    
    def filter_address(self, queryset, name, value):
        if not value:
            return queryset

        # Expected format:
        # street_name%number%number_suffix%number_end%number_end_suffix%floor%door%stair%building
        parts = (value or "").split("%")
        # Pad to 9 elements to avoid IndexError
        parts += [""] * (9 - len(parts))
        (
            street_name,
            number,
            number_suffix,
            number_end,
            number_end_suffix,
            floor,
            door,
            stair,
            building,
        ) = [p.strip() for p in parts[:9]]

        addr_filter = Q()

        # Street name
        if street_name:
            addr_filter &= Q(
                supply_point_default__address__street__name__icontains=street_name
            )

        # Street number and related fields (on StreetNumber)
        # We don't try to guess number_type here; we just match by the given fields.
        if number:
            try:
                addr_filter &= Q(
                    supply_point_default__address__street_number__number=int(number)
                )
            except ValueError:
                # If number is not an int, match it via the rendered string of StreetNumber
                addr_filter &= Q(
                    supply_point_default__address__street_number__token__iexact=number
                )

        if number_suffix:
            addr_filter &= Q(
                supply_point_default__address__street_number__number_suffix__icontains=number_suffix
            )

        if number_end:
            try:
                addr_filter &= Q(
                    supply_point_default__address__street_number__number_end=int(
                        number_end
                    )
                )
            except ValueError:
                pass

        if number_end_suffix:
            addr_filter &= Q(
                supply_point_default__address__street_number__number_end_suffix__icontains=number_end_suffix
            )

        # Address extra fields
        if floor:
            addr_filter &= Q(
                supply_point_default__address__floor__iexact=floor
            )
        if door:
            addr_filter &= Q(
                supply_point_default__address__door__iexact=door
            )
        if stair:
            addr_filter &= Q(
                supply_point_default__address__stair__icontains=stair
            )
        if building:
            addr_filter &= Q(
                supply_point_default__address__building__icontains=building
            )

        if not addr_filter:
            # If nothing was parsed correctly, return original queryset
            return queryset

        return queryset.filter(addr_filter)

    def filter_email(self, queryset, name, value):
        if not value:
            return queryset
        value = unquote(value)
        return queryset.filter(holder__contacts__email__icontains=value).distinct()

    def filter_iban(self, queryset, name, value):
        if not value:
            return queryset
        value = unquote(value)
        # Ignorar espais tant si venen enmig/al voltant del valor cercat com si l'IBAN
        # emmagatzemat els porta o no (ex: "ES48 2100 ..." o "ES4821000254...").
        normalized = re.sub(r'\s+', '', value)
        if not normalized:
            return queryset
        return queryset.annotate(
            _iban_normalized=Replace('payment__IBAN__iban', Value(' '), Value(''))
        ).filter(_iban_normalized__icontains=normalized).distinct()

    def filter_meter(self, queryset, name, value):
        """Cerca pel codi del comptador de qualsevol punt de subministrament.

        Es mira `supply_points` i no només `supply_point_default` perquè un
        contracte en pot tenir més d'un i qui busca un comptador vol trobar el
        contracte encara que no sigui el punt principal. Es cerquen els dos
        codis (`code` i `code2`), igual que fa el filtre propi de comptadors.
        """
        if not value:
            return queryset
        value = unquote(value).strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(supply_points__meter__code__icontains=value)
            | Q(supply_points__meter__code2__icontains=value)
        ).distinct()

    def no_op(self, queryset, name, value):
        return queryset

    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_variable_type(self, queryset, name, value):
        if value:
            variable_type_values = value.split(',')
            return queryset.filter(variables__type__id__in=variable_type_values).distinct()
        return queryset
    
    def filter_bonification_type(self, queryset, name, value):
        if value:
            bonification_type_values = value.split(',')
            return queryset.filter(bonifications__bonification_type__id__in=bonification_type_values).distinct()
        return queryset

    def filter_persons(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            role = self.data.get('role', 'all')
            if role == 'holder':
                return queryset.filter(holder__id__in=value_ids)
            elif role == 'owner':
                return queryset.filter(owner__id__in=value_ids)
            elif role == 'tenant':
                return queryset.filter(tenant__id__in=value_ids)
            else:
                return queryset.filter(Q(holder__id__in=value_ids) | Q(tenant__id__in=value_ids) | Q(owner__id__in=value_ids))
        return queryset