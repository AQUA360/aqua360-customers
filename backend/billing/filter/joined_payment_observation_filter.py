from django_filters import rest_framework as filters
from ..models import JoinedPaymentObservation


class JoinedPaymentObservationFilter(filters.FilterSet):
    joined_payment = filters.CharFilter(field_name='joined_payment__id', lookup_expr='exact')

    class Meta:
        model = JoinedPaymentObservation
        fields = ['joined_payment']