from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from billing.models import InvoiceSequence
from billing.serializers.value_objects_serializer import InvoiceSequenceSerializer
from billing.permissions import InvoicePermission


class InvoiceSequenceViewSet(viewsets.ModelViewSet):
    queryset = InvoiceSequence.objects.all().order_by('prefix')
    serializer_class = InvoiceSequenceSerializer
    permission_classes = [IsAuthenticated, InvoicePermission]
