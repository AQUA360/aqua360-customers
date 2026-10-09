from django_filters import rest_framework as filters
from django.db.models import Q
from ..models import MessageTemplate

class MessageTemplateFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    origin = filters.CharFilter(field_name='origin__id', lookup_expr='exact')
    
    class Meta:
        model = MessageTemplate
        fields = ['search', 'origin']
   
    def filter_search(self, queryset, name, value):
            
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) |
            Q(origin__name__icontains=value) 
        )
    