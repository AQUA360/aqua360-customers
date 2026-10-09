from django_filters import rest_framework as filters
from django.db.models import Q
from logger.models import LogInvoiceDataChange

class LogInvoiceDataChangeFilter(filters.FilterSet):
    object = filters.NumberFilter(field_name='object__id')
    
    class Meta:
        model = LogInvoiceDataChange
        fields = ["object","timestamp"]
        
