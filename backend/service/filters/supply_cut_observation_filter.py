from django_filters import rest_framework as filters
from ..models import SupplyCutObservation

class SupplyCutObservationFilter(filters.FilterSet):
    supply_cut_id = filters.CharFilter(field_name='supply_cut__id', lookup_expr='exact')

    class Meta:
        model = SupplyCutObservation
        fields = ['supply_cut']