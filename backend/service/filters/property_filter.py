from django_filters import rest_framework as filters
from service.models import Property, SupplyPoint
from django.db.models import Q, Exists, OuterRef

class PropertyFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    search_by_address = filters.CharFilter(method='filter_address')
    only_unassigned = filters.BooleanFilter(method='filter_only_unassigned', label='Only properties without position')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    
    class Meta:
        model = Property
        fields = ['search']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) | Q(name__icontains=value)
        )
    
    def filter_only_unassigned(self, queryset, name, value):
        if value:
            queryset = queryset.filter(route_position=None)
        return queryset
    
    def filter_exploitation(self, queryset, name, value):
        if value:
            on_exploitation = Exists(
                SupplyPoint.objects.filter(
                    property_id=OuterRef("pk"),
                    connection__exploitation_id=value,
                )
            )
            no_supply_points = ~Exists(
                SupplyPoint.objects.filter(property_id=OuterRef("pk"))
            )
            return queryset.filter(on_exploitation | no_supply_points)
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

        # Property uses address_street / address_street_number / address_city
        if street_name:
            addr_filter &= Q(
                address_street__name__icontains=street_name
            )

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

        # Property has no floor/door/stair/building fields in the model, so we ignore those

        if not addr_filter:
            return queryset

        return queryset.filter(addr_filter).distinct()