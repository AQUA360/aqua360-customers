from django_filters import rest_framework as filters
from ..models import ClusterObservation

class ClusterObservationFilter(filters.FilterSet):
    connection_id = filters.CharFilter(field_name='cluster__id', lookup_expr='exact')

    class Meta:
        model =ClusterObservation
        fields = ['cluster']