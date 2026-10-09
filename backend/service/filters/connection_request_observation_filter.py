from django_filters import rest_framework as filters
from ..models import ConnectionRequestObservation

class ConnectionRequestObservationFilter(filters.FilterSet):
    connection_request_id = filters.CharFilter(field_name='connection_request__id', lookup_expr='exact')

    class Meta:
        model =ConnectionRequestObservation
        fields = ['connection_request']