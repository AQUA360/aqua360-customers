from django_filters import rest_framework as filters
from ..models import FraudImage

class FraudImageFilter(filters.FilterSet):
    fraud_report = filters.CharFilter(field_name='fraud_report__id', lookup_expr='exact')

    class Meta:
        model = FraudImage
        fields = ['fraud_report']