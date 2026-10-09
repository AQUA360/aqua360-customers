from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from billing.models import BankRNDDocument, InvoiceClass, InvoiceSuppressionReason, ReadingAlert, RejectMotive, RejectMotiveType
from billing.serializers.value_objects_serializer import BankRNDDocumentSerializer, InvoiceClassSerializer, InvoiceSuppressionReasonSerializer, ReadingAlertSerializer, RejectMotiveSerializer, RejectMotiveTypeSerializer
from billing.permissions import InvoicePermission ,ReadingPermission, PaymentPermission
class InvoiceClassViewSet(viewsets.ModelViewSet):
    queryset = InvoiceClass.objects.all()
    serializer_class = InvoiceClassSerializer
    permission_classes = [IsAuthenticated, InvoicePermission]

class ReadingAlertViewSet(viewsets.ModelViewSet):
    queryset = ReadingAlert.objects.all()
    serializer_class = ReadingAlertSerializer 
    permission_classes = [IsAuthenticated, ReadingPermission]

class RejectMotiveViewSet(viewsets.ModelViewSet):
    queryset = RejectMotive.objects.all()
    serializer_class = RejectMotiveSerializer
    permission_classes = [IsAuthenticated, PaymentPermission]

class RejectMotiveTypeViewSet(viewsets.ModelViewSet):
    queryset = RejectMotiveType.objects.all()
    serializer_class = RejectMotiveTypeSerializer
    permission_classes = [IsAuthenticated, PaymentPermission]

class InvoiceSuppressionReasonViewSet(viewsets.ModelViewSet):
    queryset = InvoiceSuppressionReason.objects.all()
    serializer_class = InvoiceSuppressionReasonSerializer
    permission_classes = [IsAuthenticated, InvoicePermission]

class BankRNDDocumentViewSet(viewsets.ModelViewSet):
    queryset = BankRNDDocument.objects.all()
    serializer_class = BankRNDDocumentSerializer
    permission_classes = [IsAuthenticated, PaymentPermission]