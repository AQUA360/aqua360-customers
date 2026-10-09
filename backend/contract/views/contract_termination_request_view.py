from django.conf import settings
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework import status

from auth.permissions import PermissionManager
from contract.filters import ContractTerminationRequestFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.http import JsonResponse
from coredata.models import ConfigProject
from contract.models import (ContractTerminationRequest, ContractTerminationStatus, ContractStatus)
from contract.serializers.contract_termination_request_serializer import (ContractTerminationRequestSerializer, ContractTerminationRequestSaveSerializer, ContractTerminationRequestListSerializer)
from contract.permissions import ContractTerminationRequestPermission
from contract.utils.contract_termination_service import getTerminationDocument
from documentmanager.utils.main_utils import upload_document
class ContractTerminationRequestViewSet(viewsets.ModelViewSet):
    queryset = ContractTerminationRequest.objects.filter(is_active=True).all().order_by('-created_at')
    permission_classes = [IsAuthenticated, ContractTerminationRequestPermission]
    filterset_class = ContractTerminationRequestFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = '__all__'
    ordering_fields = ['token', 'created_at', 'contract', 'contract__supply_point_default', 'contract__holder', 'status', 'approved_at']
    """ ordering_fields = '__all__' """

    def get_serializer_class(self):
        if self.request.method in ['GET']:
            if self.action == 'list':  # Corresponds to GET / (list view)
                return ContractTerminationRequestListSerializer
            elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
                return ContractTerminationRequestSerializer
            return ContractTerminationRequestSerializer
        return ContractTerminationRequestSaveSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = ContractTerminationRequestSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        file = request.data.pop('termination_file', None)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if file:
            service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
            document = upload_document(file[0], 'CONTRACT', 'CONTRACT', instance.contract.id, instance.contract.token, '', service, file[0].name, instance.created_at)
            validated_data = serializer.validated_data
            validated_data['termination_file'] = document
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = ContractTerminationRequestSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    @action(detail=True, methods=['get'], url_path='download')
    def download_pdf(self, request, pk=None):
        instance = self.get_object()
        file_url = getTerminationDocument(instance, request)
        return JsonResponse({"pdf_url": file_url})
    
    
    @action(detail=True, methods=['put'], url_path='cancel')
    def cancel_termination(self, request, pk=None):
        instance = self.get_object()
        cancel_status = ContractTerminationStatus.objects.get(token=ConfigProject.objects.get(token='contract_termination_cancelled_token').value)
        try:
            instance.status = cancel_status
            instance.save()
            readings = instance.readings.all()
            readings.update(is_control=True)
            contract = instance.contract
            contract.status = ContractStatus.objects.get(token=ConfigProject.objects.get(token='contract_active_token').value)
            contract.termination_date = None
            contract.save()

            # reset bails status back to "No Retornat" if the termination is cancelled
            from contract.models import Bail, BailStatus
            from logger.models import LogBailStatus
            from django.utils import timezone
            
            pending_bail_token = ConfigProject.objects.get(token='bail_status_pending_token').value
            unreturned_bail_token = ConfigProject.objects.get(token='bail_status_unreturned_token').value
            unreturned_status = BailStatus.objects.get(token=unreturned_bail_token)
            
            bails = Bail.objects.filter(contract=contract, status__token=pending_bail_token)
            for bail in bails:
                prev_status = bail.status
                bail.status = unreturned_status
                bail.return_date = None
                bail.invoice = None
                bail.save()
                
                LogBailStatus.objects.create(
                    object=bail,
                    previous_status=prev_status,
                    current_status=unreturned_status,
                    user=request.user,
                    timestamp=timezone.now(),
                    observation="Baixa de contracte cancel·lada, fiança restablerta a No Retornat"
                )
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serialized_instance = ContractTerminationRequestSerializer(instance)
        return Response(serialized_instance.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        pk = request.query_params.get('id')
        if pk:
            from django.contrib.auth.models import Group
            user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
            if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
                return Response( None, status=status.HTTP_403_FORBIDDEN )
            group = Group.objects.filter(id=pk).first()
            if not group:
                return Response( None, status=status.HTTP_404_NOT_FOUND )
            group_permissions = PermissionManager.get_model_group_permissions(group, 'contractterminationrequest')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'contractterminationrequest', 'contract')
        return Response(permissions, status=status.HTTP_200_OK)
    
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()