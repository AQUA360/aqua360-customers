from django_filters import rest_framework as filters
from django.db.models import Q, Count, Subquery, OuterRef
from service.models import Meter, SupplyPoint
from django.db.models import Q
from functools import reduce
from operator import and_

class MeterFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    search_by_address = filters.CharFilter(method='filter_address')
    status = filters.CharFilter(method='filter_status')
    supply_point_status = filters.CharFilter(method='filter_supply_point_status')
    no_supply_points = filters.BooleanFilter(method='filter_no_supply_points', label='No Supply Points')
    exclude = filters.NumberFilter(method='filter_exclude', label='Exclude meter with certain id')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    is_general = filters.BooleanFilter(field_name='is_general', label='Is General')
    is_compound = filters.BooleanFilter(field_name='is_compound', label='Is Compound')
    is_property = filters.BooleanFilter(field_name='is_property', label='Is Property')
    remote_reading_type = filters.CharFilter(method='filter_remote_reading_type')
    remote_reading_history = filters.NumberFilter(method='filter_remote_reading_history')
    
    class Meta:
        model = Meter
        fields = ['search','status', 'supply_point_status', 'is_general', 'is_compound', 'is_property', 'exploitation', 'remote_reading_type', 'remote_reading_history']

    def filter_search(self, queryset, name, value):
        if not value or not value.strip():
            return queryset

        search_terms = value.split()
        if not search_terms:
            return queryset
        term_queries = []
        for term in search_terms:
            # Base query components (text fields only)
            query_components = [
                Q(code__icontains=term),
                Q(code2__icontains=term),
                Q(token__icontains=term),
                Q(supply_points__address__street__name__icontains=term),
                Q(supply_points__address__street_number__number_suffix__icontains=term),
                Q(supply_points__address__floor__icontains=term)
                # Q(supply_points__address__door__icontains=term)
                # Q(supply_points__address__stair__icontains=term)
                # Q(supply_points__address__building__icontains=term)
            ]
            
            # Add number-related queries only if term is a number
            if term.isdigit():
                # Convert string to int for exact match on IntegerField
                term_int = int(term)
                query_components.extend([
                    Q(supply_points__address__street_number__number=term_int),
                    Q(supply_points__address__street_number__number_end=term_int)
                ])
            
            term_query = reduce(lambda x, y: x | y, query_components)
            term_queries.append(term_query)
        
        final_query = reduce(and_, term_queries)
        return queryset.filter(final_query).distinct()
        
        
        # return queryset.filter(
        #     Q(code__icontains=value) |
        #     Q(supply_points__address__street__name__icontains=value)
        # ).distinct()
    
    def filter_remote_reading_history(self, queryset, name, value):
        if value:
            val_number = int(value)
            return queryset.filter(
                has_ever_been_remote= val_number > 0,
                has_remote_reading= val_number > 1
                )
        return queryset
    
    def filter_remote_reading_type(self, queryset, name, value):
        if value:
            return queryset.filter(remote_reading_type=value, has_ever_been_remote=True)
        return queryset
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
    def filter_supply_point_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            first_supply_point_status = SupplyPoint.objects.filter(
                meter=OuterRef('pk')
            ).order_by('id').values('status__id')
            
            queryset = queryset.annotate(
                supply_point_status_id=Subquery(first_supply_point_status[:1])
            ).filter(supply_point_status_token__in=status_values)
        return queryset

    def filter_no_supply_points(self, queryset, name, value):
        if value:
            queryset = queryset.annotate(num_supply_points=Count('supply_points')).filter(num_supply_points=0)
        return queryset
    def filter_exclude(self, queryset, name, value):
        if value:
            queryset = queryset.exclude(id=value)
        return queryset

    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(supply_points__connection__exploitation__id=value) |
                Q(supply_points__connection__exploitation__isnull=True)
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
                supply_points__address__street__name__icontains=street_name
            )

        # Street number and related fields (on StreetNumber)
        # We don't try to guess number_type here; we just match by the given fields.
        if number:
            try:
                addr_filter &= Q(
                    supply_points__address__street_number__number=int(number)
                )
            except ValueError:
                # If number is not an int, match it via the rendered string of StreetNumber
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

        # Address extra fields
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
            # If nothing was parsed correctly, return original queryset
            return queryset

        return queryset.filter(addr_filter).distinct()