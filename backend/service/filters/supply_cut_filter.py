from django_filters import rest_framework as filters
from rest_framework.filters import OrderingFilter
from service.models import SupplyCut, SupplyCutStatus
from django.db.models import Q

class SupplyCutOrderingFilter(OrderingFilter):
    """OrderingFilter that honours the `ordering_fields` dict values.

    DRF's OrderingFilter treats `ordering_fields` only as a whitelist of
    raw terms (a dict is collapsed to (key, key)) and then passes those
    terms straight to `queryset.order_by()`, so a term like `status_name`
    (which is not a model field) crashes with a FieldError. This subclass
    remaps each validated term through the dict values, e.g.
    `status_name` -> `status__name`.
    """

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            return ordering
        fields_map = getattr(view, 'ordering_fields', None) or {}
        mapped = []
        for term in ordering:
            desc = term.startswith('-')
            key = term[1:] if desc else term
            if key in fields_map:
                mapped.append(('-' if desc else '') + fields_map[key])
        return mapped or ordering

class SupplyCutFilter(filters.FilterSet):
    status = filters.BaseInFilter(field_name='status', method='filter_status', lookup_expr='in')
    supply_point = filters.NumberFilter(field_name='supply_points__id', lookup_expr='exact')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    search_by_address = filters.CharFilter(method='filter_address')
    source = filters.CharFilter(field_name='source', lookup_expr='exact')
    
    class Meta:
        model = SupplyCut
        fields = ['status', 'supply_point', 'exploitation', 'source']

    def filter_status(self, queryset, name, value):
        # The status FK resolves to an integer id, so filtering with a
        # non-numeric token (name or CSV split artefact) used to raise a
        # ValueError (500). Resolve ids, tokens and names against the
        # status table and never crash on anything else.
        values = [str(v).strip() for v in value if str(v).strip()]
        if not values:
            return queryset.none()
        digits = [v for v in values if v.isdigit()]
        textual = [v for v in values if not v.isdigit()]
        status_ids = set()
        if digits:
            status_ids.update(SupplyCutStatus.objects.filter(id__in=digits).values_list('id', flat=True))
            # Some statuses use numeric-looking tokens (e.g. '0'); do not
            # drop them just because the value looks like an id.
            status_ids.update(SupplyCutStatus.objects.filter(token__in=digits).values_list('id', flat=True))
        if textual:
            status_ids.update(
                SupplyCutStatus.objects.filter(Q(token__in=textual) | Q(name__in=textual)).values_list('id', flat=True)
            )
        if not status_ids:
            return queryset.none()
        return queryset.filter(status__in=status_ids)

    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(supply_points__connection__exploitation__id=value) 
            ).distinct()
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

        # SupplyCut -> supply_points -> address
        if street_name:
            addr_filter &= Q(
                supply_points__address__street__name__icontains=street_name
            )

        if number:
            try:
                addr_filter &= Q(
                    supply_points__address__street_number__number=int(number)
                )
            except ValueError:
                addr_filter &= Q(
                    supply_points__address__street_number__token__iexact=number
                )

        if number_suffix:
            addr_filter &= Q(
                supply_points__address__street_number__number_suffix__icontains=number_suffix
            )

        if number_end:
            try:
                addr_filter &= Q(
                    supply_points__address__street_number__number_end=int(
                        number_end
                    )
                )
            except ValueError:
                pass

        if number_end_suffix:
            addr_filter &= Q(
                supply_points__address__street_number__number_end_suffix__icontains=number_end_suffix
            )

        if floor:
            addr_filter &= Q(
                supply_points__address__floor__iexact=floor
            )
        if door:
            addr_filter &= Q(
                supply_points__address__door__iexact=door
            )
        if stair:
            addr_filter &= Q(
                supply_points__address__stair__icontains=stair
            )
        if building:
            addr_filter &= Q(
                supply_points__address__building__icontains=building
            )

        if not addr_filter:
            return queryset

        return queryset.filter(addr_filter).distinct()