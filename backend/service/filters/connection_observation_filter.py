from django_filters import rest_framework as filters
from ..models import ConnectionObservation

class ConnectionObservationFilter(filters.FilterSet):
    connection_id = filters.CharFilter(field_name='connection__id', lookup_expr='exact')

    class Meta:
        model =ConnectionObservation
        fields = ['connection']