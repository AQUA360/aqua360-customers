from django_filters import rest_framework as filters
from ..models import IncidentObservation

class IncidentObservationFilter(filters.FilterSet):
    incident = filters.CharFilter(field_name='incident__id', lookup_expr='exact')

    class Meta:
        model = IncidentObservation
        fields = ['incident']