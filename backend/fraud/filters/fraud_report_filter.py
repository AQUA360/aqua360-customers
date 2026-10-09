from django_filters import rest_framework as filters
from ..models import FraudReport

class FraudReportFilter(filters.FilterSet):
    fraud = filters.CharFilter(field_name='fraud__id', lookup_expr='exact')

    class Meta:
        model = FraudReport
        fields = ['fraud']