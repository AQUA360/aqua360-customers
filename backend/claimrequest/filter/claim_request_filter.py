from django_filters import rest_framework as filters
from ..models import ClaimRequest
from django.db.models import Q

class ClaimRequestFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    step = filters.CharFilter(method='filter_step')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    contract = filters.CharFilter(method='filter_contract')
    user = filters.CharFilter(field_name='user__id', lookup_expr='exact')
    is_communication = filters.BooleanFilter(method='filter_is_communication')
    
    class Meta:
        model = ClaimRequest
        fields = ['search', 'status', 'user', 'contract', 'exploitation']
   
    def filter_search(self, queryset, name, value):
        # Validar el valor de cerca
        if not value or value == '[object PointerEvent]':
            return queryset
            
        return queryset.filter(
            Q(token__icontains=value) |
            Q(current_step__step_template__token__icontains=value) |
            Q(current_step__step_template__name__icontains=value) |
            Q(payments__token__icontains=value) |
            Q(description__icontains=value) |
            Q(status__name__icontains=value)
        )
    
    def filter_status(self, queryset, name, value):
        if value:
            values = value.split(',')
            return queryset.filter(status__token__in=values)
        return queryset
    
    def filter_step(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(current_step__step_template__id__in=value_ids)
        return queryset 

    def filter_contract(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(payments__contract__id__in=value_ids)
        return queryset

    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(payments__contract__supply_point_default__connection__exploitation__id=value)
            ).distinct()
        return queryset

    def filter_is_communication(self, queryset, name, value):
        
        return queryset
        
        #TODO CORRECTLY IMPLEMENT THIS FILTER
        
        if value:
            return queryset.filter(current_step__document_type__isnull=False)
        return queryset