# coredata/views/return_reason_view.py
from rest_framework import viewsets
from coredata.models import ReturnReason
from coredata.serializers import ReturnReasonSerializer

class ReturnReasonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReturnReason.objects.all()
    serializer_class = ReturnReasonSerializer