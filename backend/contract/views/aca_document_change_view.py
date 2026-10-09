from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework import status
from contract.models import ACADocumentChange
from contract.serializers.aca_document_serializer import ACADocumentChangeSerializer
from ..utils.aca_document_service import process_document
from datetime import datetime
from contract.permissions import ContractPermission
class ACADocumentChangeViewSet(viewsets.ModelViewSet):
    queryset = ACADocumentChange.objects.all().order_by('created_at')
    serializer_class = ACADocumentChangeSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    search_fields = []
    ordering_fields = []
