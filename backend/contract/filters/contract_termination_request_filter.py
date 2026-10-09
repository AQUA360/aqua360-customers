from django_filters import rest_framework as filters

from coredata.models import ConfigProject
from ..models import ContractTerminationRequest
from django.db.models import Q

class ContractTerminationRequestFilter(filters.FilterSet):
    status = filters.CharFilter(method='filter_status')
    type = filters.CharFilter(method='filter_type')
    exploitation = filters.NumberFilter(field_name='contract__supply_point_default__connection__exploitation__id', lookup_expr='exact')
    no_invoice = filters.BooleanFilter(method='filter_no_invoice')
    search = filters.CharFilter(method='filter_search')
    search_by_address = filters.CharFilter(method='filter_address')

    class Meta:
        model = ContractTerminationRequest
        fields = ['status', 'type', 'exploitation', 'search', 'no_invoice']
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_type(self, queryset, name, value):
        if value:
            type_values = value.split(',')
            return queryset.filter(type__id__in=type_values)
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

        # Cada paraula ha de coincidir en algun camp (AND entre paraules) perque
        # "Nom Cognom" pugui creuar name i surname de la persona.
        terms = value.split()
        if not terms:
            return queryset

        for term in terms:
            queryset = queryset.filter(
                Q(token__icontains=term) |
                Q(contract__token__icontains=term) |
                Q(person__name__icontains=term) |
                Q(person__surname__icontains=term) |
                Q(person__token__icontains=term) |
                Q(contract__supply_point_default__address__address_search__icontains=term)
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

        # Address is taken from the related contract's default supply point
        # Contract -> supply_point_default -> address
        if street_name:
            addr_filter &= Q(
                contract__supply_point_default__address__street__name__icontains=street_name
            )

        if number:
            try:
                addr_filter &= Q(
                    contract__supply_point_default__address__street_number__number=int(number)
                )
            except ValueError:
                addr_filter &= Q(
                    contract__supply_point_default__address__street_number__token__iexact=number
                )

        if number_suffix:
            addr_filter &= Q(
                contract__supply_point_default__address__street_number__number_suffix__icontains=number_suffix
            )

        if number_end:
            try:
                addr_filter &= Q(
                    contract__supply_point_default__address__street_number__number_end=int(
                        number_end
                    )
                )
            except ValueError:
                pass

        if number_end_suffix:
            addr_filter &= Q(
                contract__supply_point_default__address__street_number__number_end_suffix__icontains=number_end_suffix
            )

        if floor:
            addr_filter &= Q(
                contract__supply_point_default__address__floor__iexact=floor
            )
        if door:
            addr_filter &= Q(
                contract__supply_point_default__address__door__iexact=door
            )
        if stair:
            addr_filter &= Q(
                contract__supply_point_default__address__stair__icontains=stair
            )
        if building:
            addr_filter &= Q(
                contract__supply_point_default__address__building__icontains=building
            )

        if not addr_filter:
            return queryset

        return queryset.filter(addr_filter)