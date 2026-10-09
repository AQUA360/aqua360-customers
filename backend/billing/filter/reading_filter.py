from django_filters import rest_framework as filters
from ..models import Reading
from django.db.models import Q
from functools import reduce
from operator import and_
from billing.utils.reading_filters import PENDING_READING_FILTER


class ReadingFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    contract = filters.CharFilter(method='filter_contract')
    supply_point = filters.CharFilter(field_name='supply_point__id', lookup_expr='exact')
    meter = filters.CharFilter(field_name='meter__id', lookup_expr='exact')
    alert = filters.CharFilter(method='filter_alert')
    reader_alert = filters.CharFilter(method='filter_reader_alert')
    route = filters.CharFilter(method='filter_route')
    previous_leak = filters.BooleanFilter(method='filter_previous_leak')
    leak = filters.BooleanFilter(method='filter_leak')
    is_control = filters.BooleanFilter(field_name='is_control')
    exploitation = filters.NumberFilter(field_name='supply_point__connection__exploitation__id', lookup_expr='exact')
    billed = filters.BooleanFilter(method='filter_billed')
    class Meta:
        model = Reading
        fields = ['search', 'contract', 'supply_point', 'meter', 'alert', 'reader_alert', 'leak', 'previous_leak', 'is_control', 'exploitation', 'billed']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        search_terms = value.split()
        term_queries = []
        for term in search_terms:
            term_query = (
                Q(meter__token__icontains=term) |
                Q(token__icontains=term) |
                Q(contract__token__icontains=term) |
                Q(supply_point__token__icontains=term) |
                Q(supply_point__name__icontains=term) |
                Q(supply_point__address__city__name__icontains=term) |
                Q(supply_point__address__street__name__icontains=term) |
                Q(supply_point__address__street_number__number__icontains=term) |
                Q(supply_point__address__street_number__number_end__icontains=term) |
                Q(supply_point__address__street_number__number_suffix__icontains=term) |
                Q(supply_point__address__street_number__number_end_suffix__icontains=term) |
                Q(supply_point__address__street_number__number_type__type__icontains=term) |
                Q(supply_point__address__street_number__number_type__description__icontains=term) |
                Q(supply_point__address__street_number__number_type__type__icontains=term)
            )
            term_queries.append(term_query)
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query)
    
    def filter_contract(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(contract__id__in=value_ids)
        return queryset
    
    def filter_alert(self, queryset, name, value):
        if value == 'any':
            return queryset.filter(alert__isnull=False)
        elif value == 'null':
            return queryset.filter(alert__isnull=True)
        elif value == 'warning_date_range':
            return queryset
        else:
            return queryset.filter(alert__name=value)
    
    def filter_reader_alert(self, queryset, name, value):
        if value == 'any':
            return queryset.filter(reader_alert__isnull=False)
        elif value == 'null':
            return queryset.filter(reader_alert__isnull=True)
        else:
            return queryset.filter(reader_alert__name=value)

    def filter_leak(self, queryset, name, value):
        if value:
            return queryset.filter(leak_value__gt=0)
        return queryset
    
    def filter_previous_leak(self, queryset, name, value):
        if value:
            return queryset.filter(previous_reading__leak_value__gt=0)
        return queryset
    
    def filter_route(self, queryset, name, value):
        if value and value != 'undefined':
            return queryset.filter(
                Q(supply_point__property__route_position__route__id=value)
            )
        return queryset
    
    def filter_billed(self, queryset, name, value):
        if value:
            return queryset.filter(invoices__type_final='F').distinct()
        return queryset.filter(PENDING_READING_FILTER).distinct()