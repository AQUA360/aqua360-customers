# contract/views/contract_request_view.py
from rest_framework.decorators import action
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.views import APIView
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat
from django.utils.translation import gettext as _

from contract.filters.contract_request_filter import ContractRequestFilter
from contract.middleware import set_current_user
from contract.models import (ContractRequest, ContractDocumentationType, ContractRequestDocumentation)
from contract.serializers.contract_request_serializer import (ContractRequestSerializer, ContractRequestSaveSerializer, ContractRequestListSerializer)
from contract.utils.contract_service import contract_create
from contract.utils.contract_token_service import generate_contract_request_token
from coredata.utils.name_utils import generate_token, check_token_exists
from coredata.utils import name_utils as name_utils_module
from documentmanager.utils.main_utils import upload_document
from django.contrib.auth.models import User
from auth.permissions import PermissionManager
from service.models import MeterCaliber


class ContractRequestViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows ContractRequest to be viewed or edited.
    """
    queryset = ContractRequest.objects.filter(is_active=True).all().order_by('created_at')
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    required_module = 'contract'
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = ContractRequestFilter
    search_fields = [
        'token', 'holder__token', 'holder__name',
        'supply_point_default__token', 'supply_point_default__name'
        ]
    ordering_fields = ['token', 'status', 'created_at']
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            if self.action == 'list':  # Corresponds to GET / (list view)
                return ContractRequestListSerializer
            elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
                return ContractRequestSerializer
        return ContractRequestSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        # name_utils_personalized needs create-time fields; contract_token_service
        # only calls generate_token(ContractRequest) with no kwargs.
        using_personalized = (
            getattr(name_utils_module.generate_token, '__module__', '')
            .endswith('name_utils_personalized')
        )
        if using_personalized:
            request.data['token'] = check_token_exists(
                generate_token(
                    ContractRequest,
                    use_type_id=request.data.get('use_type'),
                    client_type_id=request.data.get('client_type'),
                    company_id=request.data.get('company'),
                    is_change_of_name=request.data.get('is_change_of_name'),
                ),
                ContractRequest,
            )
        else:
            request.data['token'] = generate_contract_request_token()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = ContractRequestSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    @action(detail=True, methods=['post'], url_path='regenerate-token')
    def regenerate_token(self, request, pk=None):
        """Calcula un nou token per a la ContractRequest sense persistir-lo."""
        set_current_user(request.user)
        instance = self.get_object()

        candidate = generate_token(
            ContractRequest,
            use_type_id=getattr(instance.use_type, 'id', None),
            client_type_id=getattr(instance.client_type, 'id', None),
            company_id=getattr(instance.company, 'id', None),
            is_change_of_name=instance.is_change_of_name,
        )

        while ContractRequest.objects.filter(token=candidate).exclude(pk=instance.pk).exists():
            try:
                candidate = f'{int(candidate) + 1:05d}'
            except (TypeError, ValueError):
                candidate = check_token_exists(candidate, ContractRequest)
                break

        return Response({'token': candidate}, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        file = request.data.pop('contract_file', None)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        if file:
            service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
            document = upload_document(file[0], 'CONTRACT', 'CONTRACT', instance.id, instance.token, '', service, file[0].name, instance.created_at)
            validated_data = serializer.validated_data
            validated_data['contract_file'] = document
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = ContractRequestSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    
    @action(detail=True, methods=['put'], url_path='save-file')
    def upload_contract_request_document(self, request, pk):
        set_current_user(request.user)
        instance = self.get_object()
        file = request.FILES.getlist('file') or None
        contract_type_id = request.data.get('contract_type', None)
        text = request.data.get('text', None)

        try:
            contract_type = ContractDocumentationType.objects.get(id=contract_type_id)
        except Exception as e:
            contract_type = None

        if not file:
            raise ValidationError("File is required")
        service = settings.DOCUMENT_MANAGER_SERVICES.get("contract")
        document = upload_document(file[0], 'CONTRACT', 'CONTRACT', instance.id, instance.token, '', service, file[0].name, instance.created_at)

        new_documentation = ContractRequestDocumentation.objects.create(
            contract_request=instance,
            file=document,
            contract_type=contract_type,
            text=text,
        )
        serializer = ContractRequestSerializer(instance, context=self.get_serializer_context())

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='save-documentation')
    def save_documentation(self, request, pk):
        set_current_user(request.user)
        instance = self.get_object()
        contract_type_id = request.data.get('contract_type', None)
        text = request.data.get('text', None)

        try:
            contract_type = ContractDocumentationType.objects.get(id=contract_type_id)
        except Exception:
            contract_type = None

        ContractRequestDocumentation.objects.create(
            contract_request=instance,
            contract_type=contract_type,
            text=text,
        )
        serializer = ContractRequestSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['put'], url_path='set-requested-meter-caliber')
    def set_requested_meter_caliber(self, request, pk):
        set_current_user(request.user)
        instance = self.get_object()
        requested_meter_caliber_id = request.data.get('requested_meter_caliber', None)
        meter_mode = request.data.get('meter_mode', None)
        update_fields = []

        if requested_meter_caliber_id:
            try:
                meter_caliber = MeterCaliber.objects.get(id=requested_meter_caliber_id)
                instance.requested_meter_caliber = meter_caliber
                update_fields.append('requested_meter_caliber')
            except MeterCaliber.DoesNotExist:
                return Response({"error": _("MeterCaliber not found")}, status=status.HTTP_404_NOT_FOUND)
        else:
            instance.requested_meter_caliber = None
            update_fields.append('requested_meter_caliber')

        if meter_mode is not None:
            valid_meter_modes = dict(ContractRequest.METER_MODE_CHOICES)
            if meter_mode not in valid_meter_modes:
                return Response({"error": _("Invalid meter_mode")}, status=status.HTTP_400_BAD_REQUEST)
            instance.meter_mode = meter_mode
            update_fields.append('meter_mode')

        instance.save(update_fields=update_fields)

        serializer = ContractRequestSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='send-for-signing')
    def send_for_signing(self, request, pk=None):
        from integrations.outbound.signing.exceptions import SigningApiError
        from integrations.outbound.signing.services import create_contract_request_signing_session

        set_current_user(request.user)
        instance = self.get_object()
        try:
            result = create_contract_request_signing_session(
                instance,
                recipient_name=request.data.get('recipient_name'),
                recipient_email=request.data.get('recipient_email'),
                recipient_phone=request.data.get('recipient_phone'),
                callback_url=request.data.get('callback_url'),
                force=str(request.data.get('force', '')).lower() in ('true', '1', 'yes'),
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except SigningApiError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'], url_path='validate-data')
    def validate_data(self, request, pk=None):
        instance = self.get_object()
        from contract.utils.contract_request_service import contract_request_validate_data
        errors = contract_request_validate_data(instance)
        return Response({
            "valid": len(errors) == 0,
            "errors": errors
        }, status=status.HTTP_200_OK)
    
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'contractrequest')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'contractrequest', 'contract')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()
    
class ContractRequestCreateContractView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ContractRequest.objects.all()
    
    def put(self, request, id):
        try:
            print("CONTRACT REQUEST CREATE CONTRACT VIEW")
            contract_request = ContractRequest.objects.get(id=id)
            from contract.utils.contract_request_service import contract_request_validate_data
            errors = contract_request_validate_data(contract_request)
            if errors:
                return Response({
                    "error": "La sol·licitud conté dades incompletes o incorrectes per poder crear el contracte.",
                    "errors": errors
                }, status=status.HTTP_400_BAD_REQUEST)
            contract_request = contract_create(request.user, id)
            serializer = ContractRequestSerializer(contract_request, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ContractRequest.DoesNotExist:
            return Response({"error": "ContractRequest not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
