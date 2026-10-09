from django_filters import rest_framework as filters
from ..models import IncidentDocumentation

class IncidentDocumentationFilter(filters.FilterSet):
    incident_report = filters.CharFilter(field_name='incident_report__id', lookup_expr='exact')

    class Meta:
        model = IncidentDocumentation
        fields = ['incident_report']