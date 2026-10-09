# Contract_request_filter.py

from django_filters import rest_framework as filters
from django.db.models import Q
from contract.models import ContractRequest
from functools import reduce
from operator import and_

from coredata.models import ConfigProject

class ContractRequestFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    search_by_address = filters.CharFilter(method='filter_address')
    status = filters.CharFilter(method='filter_status')
    exploitation = filters.NumberFilter(field_name='supply_point_default__connection__exploitation__id', lookup_expr='exact')
    category = filters.CharFilter(method='filter_category')
    client_type = filters.CharFilter(method='filter_client_type')
    use_type = filters.CharFilter(method='filter_use_type')
    no_invoice = filters.BooleanFilter(method='filter_no_invoice')
    
    class Meta:
        model = ContractRequest
        fields = ['search', 'status', 'category', 'client_type', 'use_type', 'exploitation', 'no_invoice']

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
    
    def filter_no_invoice(self, queryset, name, value):
        invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
        budget_type_token = ConfigProject.objects.get(token='invoice_type_budget_token').value
        if value is True:
            return queryset.filter(Q(invoice__isnull=True) | Q(invoice__type__token=budget_type_token))
        if value is False:
            return queryset.filter(invoice__isnull=False, invoice__type__token=invoice_type_token)
        return queryset
    
    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        search_terms = value.split()
        term_queries = []
        for term in search_terms:
            term_query = (
                Q(token__icontains=term) |
                Q(holder__name__icontains=term) |
                Q(holder__surname__icontains=term) |
                Q(holder__token__icontains=term) |
                Q(supply_point_default__token__icontains=term) |
                Q(supply_point_default__name__icontains=term) |
                Q(supply_point_default__address__city__name__icontains=term) |
                Q(supply_point_default__address__street__name__icontains=term) |
                Q(supply_point_default__address__street_number__number__icontains=term) |
                Q(supply_point_default__address__street_number__number_end__icontains=term) |
                Q(supply_point_default__address__street_number__number_suffix__icontains=term) |
                Q(supply_point_default__address__street_number__number_end_suffix__icontains=term) |
                Q(supply_point_default__address__street_number__number_type__type__icontains=term) |
                Q(supply_point_default__address__street_number__number_type__description__icontains=term) |
                Q(supply_point_default__address__street_number__number_type__type__icontains=term) |
                Q(category__name__icontains=term) |
                Q(client_type__name__icontains=term) |
                Q(use_type__name__icontains=term)
            )
            term_queries.append(term_query)
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
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