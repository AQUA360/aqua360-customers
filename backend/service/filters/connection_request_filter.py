# connection_request_filter.py

from django_filters import rest_framework as filters
from django.db.models import Q
from service.models import ConnectionRequest

class ConnectionRequestFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    search_by_address = filters.CharFilter(method='filter_address')
    status = filters.CharFilter(method='filter_status')
    exploitation = filters.NumberFilter(field_name='exploitation__id', lookup_expr='exact')
    
    class Meta:
        model = ConnectionRequest
        fields = ['search', 'status', 'exploitation']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        # Cada paraula ha de coincidir en algun camp (AND entre paraules) perque
        # "Nom Cognom" pugui creuar name i surname de la persona.
        terms = value.split()
        if not terms:
            return queryset

        for term in terms:
            queryset = queryset.filter(
                Q(token__icontains=term) |
                Q(address_street__name__icontains=term) |
                Q(person__name__icontains=term) |
                Q(person__surname__icontains=term)
            )
        return queryset
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

        # Street name (ConnectionRequest uses address_street)
        if street_name:
            addr_filter &= Q(
                address_street__name__icontains=street_name
            )

        # Street number and related fields (on StreetNumber)
        if number:
            try:
                addr_filter &= Q(
                    address_street_number__number=int(number)
                )
            except ValueError:
                addr_filter &= Q(
                    address_street_number__token__iexact=number
                )

        if number_suffix:
            addr_filter &= Q(
                address_street_number__number_suffix__icontains=number_suffix
            )

        if number_end:
            try:
                addr_filter &= Q(
                    address_street_number__number_end=int(
                        number_end
                    )
                )
            except ValueError:
                pass

        if number_end_suffix:
            addr_filter &= Q(
                address_street_number__number_end_suffix__icontains=number_end_suffix
            )

        # ConnectionRequest does not have floor/door/stair/building fields, so we ignore those

        if not addr_filter:
            return queryset

        return queryset.filter(addr_filter).distinct()