from django_filters import rest_framework as filters

from integrations.models import SendBatchObservation


class SendBatchObservationFilter(filters.FilterSet):
    class Meta:
        model = SendBatchObservation
        fields = ["send_batch"]
