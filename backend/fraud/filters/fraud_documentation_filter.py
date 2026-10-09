from django_filters import rest_framework as filters
from ..models import FraudDocumentation

class FraudDocumentationFilter(filters.FilterSet):
    fraud_report = filters.CharFilter(field_name='fraud_report__id', lookup_expr='exact')

    class Meta:
        model = FraudDocumentation
        fields = ['fraud_report']