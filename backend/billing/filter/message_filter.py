from django_filters import rest_framework as filters
from ..models import Message
from django.db.models import Q


class MessageFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    template = filters.NumberFilter(field_name='template__id', lookup_expr='exact')
    
    class Meta:
        model = Message
        fields = ['search', 'template']

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(token__icontains=value)
        )
    
   