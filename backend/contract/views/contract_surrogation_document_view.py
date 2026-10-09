from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from contract.models import ContractSurrogationDocument
from contract.serializers.contract_surrogation_serializer import ContractSurrogationDocumentSerializer
from contract.permissions import ContractPermission

class ContractSurrogationDocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Property to be viewed or edited.
    """
    queryset = ContractSurrogationDocument.objects.all()
    serializer_class = ContractSurrogationDocumentSerializer
    filter_backends = (DjangoFilterBackend,)
    permission_classes = [IsAuthenticated, ContractPermission]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.checked = False
        instance.file = None
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)