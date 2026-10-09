from django_filters import rest_framework as filters
from ..models import FraudObservation

class FraudObservationFilter(filters.FilterSet):
    fraud = filters.CharFilter(field_name='fraud__id', lookup_expr='exact')

    class Meta:
        model = FraudObservation
        fields = ['fraud']