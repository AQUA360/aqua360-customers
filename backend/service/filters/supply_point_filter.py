from django_filters import rest_framework as filters
from coredata.models import ConfigProject
from fraud.models import FraudStatus
from service.models import SupplyPoint
from django.db.models import Q
from functools import reduce
from operator import and_

class SupplyPointFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    token = filters.CharFilter(field_name='token', lookup_expr='icontains')
    status = filters.CharFilter(method='filter_status')
    no_meters = filters.BooleanFilter(method='filter_no_meters', label='No Meters')
    property = filters.NumberFilter(method='filter_property', label='Assigned to a certain property')
    street = filters.NumberFilter(method='filter_street')
    street_number = filters.CharFilter(method='filter_street_number', field_name="address__street_number__id", lookup_expr='exact')
    exploitation = filters.NumberFilter(field_name='connection__exploitation__id', lookup_expr='exact')
    type = filters.CharFilter(method='filter_type')
    supply_type = filters.CharFilter(method='filter_supply_type')
    placement_id = filters.CharFilter(method='filter_placement_id')
    cluster_nozzle_type = filters.CharFilter(method='filter_cluster_nozzle_type')
    is_potable = filters.BooleanFilter(field_name="is_potable", label="Is Potable")
    contract = filters.CharFilter(method='filter_contract', label='Get by contracts')
    has_fraud = filters.BooleanFilter(method="filter_current_fraud", label="Has Fraud")
    search_by_address = filters.CharFilter(method='filter_address')
    
    class Meta:
        model = SupplyPoint
        fields = [
            'search', 'status', 'token', 'cluster_nozzle_type', 
            'street', 'street_number', 'is_potable', 'contract', 
            'type', 'has_fraud', 'supply_type', 'placement_id'
            ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        search_terms = value.split()
        term_queries = []
        for term in search_terms:
            # term_query = (
            #     Q(token=term) |
            #     Q(address__street__name__icontains=term) |
            #     Q(address__street_number__number__icontains=term) |
            #     # Q(address_complete__icontains=term) |
            #     Q(cadastral=term)
            # )
            query_components = [
                Q(token=term),
                Q(address__street__name__icontains=term),
                Q(cadastral=term),
                # Search by contract token
                Q(contracts__token__icontains=term),
                Q(default_contracts__token__icontains=term),
                # Search by contract holder token
                Q(contracts__holder__token__icontains=term),
                Q(default_contracts__holder__token__icontains=term)
            ]
            
            # Add number-related queries only if term is a number
            if term.isdigit():
                # Convert string to int for exact match on IntegerField
                term_int = int(term)
                query_components.extend([
                    Q(address__street_number__number=term_int),
                    Q(address__street_number__number_end=term_int)
                ])
            
            term_query = reduce(lambda x, y: x | y, query_components)
            term_queries.append(term_query)
        
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query).distinct()
    
    def filter_current_fraud(self, queryset, name, value):
        if value is True:
            status_pending_token = ConfigProject.objects.get(token="fraud_status_pending_token").value
            status_active_token = ConfigProject.objects.get(token="fraud_status_active_token").value
            
            # Get the actual status objects
            status_pending = FraudStatus.objects.get(token=status_pending_token)
            status_active = FraudStatus.objects.get(token=status_active_token)
            
            return queryset.filter(fraud__status__in=[status_pending, status_active]).distinct()
        elif value is False:
            status_pending_token = ConfigProject.objects.get(token="fraud_status_pending_token").value
            status_active_token = ConfigProject.objects.get(token="fraud_status_active_token").value
            
            # Get the actual status objects
            status_pending = FraudStatus.objects.get(token=status_pending_token)
            status_active = FraudStatus.objects.get(token=status_active_token)
            return queryset.exclude(fraud__status__in=[status_pending, status_active]).distinct()
        return queryset
    
    def filter_type(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(type__id__in=value_ids)
        return queryset
    
    def filter_supply_type(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(supply_type__id__in=value_ids)
        return queryset

    def filter_placement_id(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(placement__id__in=value_ids)
        return queryset

    def filter_street(self, queryset, name, value):
        try:
            street_id = int(value)  # Convert to integer
            return queryset.filter(address__street__id=street_id)
        except (ValueError, TypeError):
            return queryset.none()  # Handle invalid input
        
    def filter_street_number(self, queryset, name, value):
        if value:
            street_number_ids = value.split(',')  # Split by commas
            # Convert to integers if needed
            street_number_ids = [int(id) for id in street_number_ids]
            return queryset.filter(address__street_number__id__in=street_number_ids)
        return queryset

    def filter_cluster_nozzle_type(self, queryset, name, value):
        if value:
            nozzle_type_values = value.split(',')
            return queryset.filter(cluster_nozzle__type__id__in=nozzle_type_values)
        return queryset
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_no_meters(self, queryset, name, value):
        if value is True:
            return queryset.filter(meter__isnull=True)
        return queryset
    
    def filter_property(self, queryset, name, value):
        if value:
            return queryset.filter(property__id=value)
        return queryset
    
    def filter_contract(self, queryset, name, value):
        if value:
            contract_values = value.split(',')
            return queryset.filter(
                Q(contracts__id__in=contract_values) | 
                Q(default_contracts__id__in=contract_values)
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

        # Street name
        if street_name:
            addr_filter &= Q(
                address__street__name__icontains=street_name
            )

        # Street number and related fields (on StreetNumber)
        # We don't try to guess number_type here; we just match by the given fields.
        if number:
            try:
                addr_filter &= Q(
                    address__street_number__number=int(number)
                )
            except ValueError:
                # If number is not an int, match it via the rendered string of StreetNumber
                addr_filter &= Q(
                    address__street_number__token__iexact=number
                )

        if number_suffix:
            addr_filter &= Q(
                address__street_number__number_suffix__icontains=number_suffix
            )

        if number_end:
            try:
                addr_filter &= Q(
                    address__street_number__number_end=int(
                        number_end
                    )
                )
            except ValueError:
                pass

        if number_end_suffix:
            addr_filter &= Q(
                address__street_number__number_end_suffix__icontains=number_end_suffix
            )

        # Address extra fields
        if floor:
            addr_filter &= Q(
                address__floor__iexact=floor
            )
        if door:
            addr_filter &= Q(
                address__door__iexact=door
            )
        if stair:
            addr_filter &= Q(
                address__stair__icontains=stair
            )
        if building:
            addr_filter &= Q(
                address__building__icontains=building
            )

        if not addr_filter:
            # If nothing was parsed correctly, return original queryset
            return queryset

        return queryset.filter(addr_filter)

