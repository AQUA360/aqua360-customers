from django_filters import rest_framework as filters
from ..models import SupplyPointObservation

class SupplyPointObservationFilter(filters.FilterSet):
    supply_point_id = filters.CharFilter(field_name='supply_point__id', lookup_expr='exact')

    class Meta:
        model = SupplyPointObservation
        fields = ['supply_point']