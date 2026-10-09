from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from billing.models import DocumentSEPALine
from billing.serializers.document_SEPA_serializer import DocumentSEPALineSerializer
from billing.permissions import PaymentPermission

class DocumentSEPALineViewSet(viewsets.ModelViewSet):
    queryset = DocumentSEPALine.objects.all()
    serializer_class = DocumentSEPALineSerializer
    permission_classes = [IsAuthenticated, PaymentPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = '__all__'
    ordering_fields = '__all__'
