from django_filters import rest_framework as filters
from ..models import IncidentReport
from django.db.models import Q

class IncidentReportFilter(filters.FilterSet):
    
    incident = filters.CharFilter(field_name='incident__id', lookup_expr='exact')
    
    class Meta:
        model = IncidentReport
        fields = ['incident']

    
  