from rest_framework import status
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from contract.models import (ContractRequestType)
from contract.filters.contract_request_type_filter import ContractRequestTypeFilter
from contract.serializers.contract_request_type_serializer import (ContractRequestTypeSerializer, ContractRequestTypeListSerializer)
from contract.permissions import ContractRequestPermission
class ContractRequestTypeViewSet(viewsets.ModelViewSet):
    queryset = ContractRequestType.objects.filter(is_active=True).order_by('token')
    serializer_class = ContractRequestTypeSerializer
    filterset_class = ContractRequestTypeFilter
    permission_classes = [IsAuthenticated, ContractRequestPermission]
    search_fields = ['token', 'name']
    ordering_fields = ['token', 'name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContractRequestTypeListSerializer
        return ContractRequestTypeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            # "Canvi de nom" ja no és un tipus de contractació seleccionable: es
            # detecta via ContractRequest.is_change_of_name i no ha d'aparèixer
            # al llistat junt amb Agrícola/Domèstic/etc.
            queryset = queryset.exclude(token='canvi_nom')
        return queryset
    
    @action(detail=False, methods=['post'], url_path='update-positions')
    def update_positions(self, request):
        updated_positions = []
        ids = request.data

        for new_position, id in enumerate(ids):
            instance = ContractRequestType.objects.filter(id=id).first()
            if instance:
                instance.position = new_position
                instance.save()
                updated_positions.append({
                    'id': instance.id,
                    'position': instance.position,
                    'name': instance.name,
                    'is_default': instance.is_default
                })

        return Response({
            "status": "positions updated",
            "updated": updated_positions
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='update-default')
    def update_default(self, request):
        updated_items = []
        id = request.data

        # Validar que el ID existeix
        if not ContractRequestType.objects.filter(id=id).exists():
            return Response({
                "status": "error",
                "message": "No valid ID provided."
            }, status=status.HTTP_400_BAD_BAD_REQUEST)

        # Marcar tots els ids com a no default
        ContractRequestType.objects.update(is_default=False)

        # Després marcar el que toca com a default
        default_item = ContractRequestType.objects.get(id=id)
        default_item.is_default = True
        default_item.save()
        updated_items.append({
            'id': default_item.id,
            'is_default': default_item.is_default
        })

        return Response({
            "status": "is_default updated",
            "updated": updated_items
        }, status=status.HTTP_200_OK)