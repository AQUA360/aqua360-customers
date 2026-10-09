from django_filters import rest_framework as filters
from ..models import CalendarTask
from django.db.models import Q

class CalendarTaskFilter(filters.FilterSet):
    
    year = filters.NumberFilter(method='filter_year')
    month = filters.NumberFilter(method='filter_month')
    set_date = filters.DateFilter(field_name='set_date', lookup_expr='exact')
    
    contract = filters.CharFilter(field_name='contract__id', lookup_expr='exact')
    
    class Meta:
        model = CalendarTask
        fields = ['contract', 'year', 'month', 'set_date']
   
    def filter_year(self, queryset, name, value):
        if value:
            return queryset.filter(set_date__year=value)
        return queryset
    
    def filter_month(self, queryset, name, value):
        if value:
            return queryset.filter(set_date__month=value)
        return queryset
    
        
    
  