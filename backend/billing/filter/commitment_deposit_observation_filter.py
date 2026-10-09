from django_filters import rest_framework as filters
from ..models import CommitmentDepositObservation


class CommitmentDepositObservationFilter(filters.FilterSet):
    commitment_deposit = filters.CharFilter(field_name='commitment_deposit__id', lookup_expr='exact')

    class Meta:
        model = CommitmentDepositObservation
        fields = ['commitment_deposit']