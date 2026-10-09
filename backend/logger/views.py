# Create your views here.
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.apps import apps
from django.db.models import Value, CharField, F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from logger.filters.log_claim_request_contract_change_filter import LogClaimRequestContractChangeFilter
from logger.filters.log_commitment_deposit_movement_filter import LogCommitmentDepositMovementFilter
from logger.filters.log_communication_change_filter import LogCommunicationChangeFilter
from logger.filters.log_communication_process_status_change_filter import LogCommunicationProcessStatusChangeFilter
from logger.filters.log_communication_status_change_filter import LogCommunicationStatusChangeFilter
from logger.filters.log_incident_status_change_filter import LogIncidentStatusChangeFilter
from logger.filters.log_invoice_change_status_filter import LogInvoiceChangeStatusFilter
from logger.filters.log_invoice_data_change_filter import LogInvoiceDataChangeFilter
from logger.filters.log_order_status_filter import LogOrderStatusFilter
from logger.filters.log_payment_status_filter import LogPaymentStatusChangeFilter
from logger.filters.log_connection_request_status_filter import LogConnectionRequestStatusFilter
from logger.filters.log_price_rate_change_filter import LogPriceRateChangeFilter
from logger.filters.log_product_change_filter import LogProductChangeFilter
from logger.filters.log_supply_cut_status_filter import LogSupplyCutStatusFilter
from logger.filters.log_supply_point_change_filter import LogSupplyPointChangeFilter
from logger.filters.log_contract_request_status_filter import LogContractRequestStatusFilter
from logger.filters.log_bail_status_filter import LogBailStatusFilter
from logger.filters.log_contract_total_members_change_filter import LogContractTotalMembersFilter
from logger.filters.log_contract_phones_filter import LogContractPhonesFilter
from logger.filters.log_contract_bonification_variable_change_filter import LogContractBonificationsVariablesChangeFilter
from logger.filters.log_contract_expired_bonifications_variables_filter import LogContractExpiredBonificationsVariablesFilter
from logger.filters.log_fraud_status_change_filter import LogFraudStatusChangeFilter
from logger.filters.log_reading_change_filter import LogReadingChangeFilter
from logger.filters.log_joined_payment_status_filter import LogJoinedPaymentStatusChangeFilter
from logger.filters.log_contract_data_change_filter import LogContractDataChangeFilter

from contract.models import ContractDataChange
from logger.serializers import LogContractDataChangeSerializer, LogPriceRateChangeSerializer, LogProductChangeSerializer

from logger.models import LogBailStatus, LogClaimRequestContractChange, LogCommitmentDepositMovement, LogCommunicationChange, LogCommunicationProcessStatusChange, LogCommunicationStatusChange, LogConnectionStatus,LogConnectionRequestStatus, LogIncidentStatusChange, LogInvoiceDataChange, LogOrderStatus, LogPaymentStatusChange, LogPriceRateChange, LogProductChange, LogSupplyCutStatus, LogSupplyPointChange, LogContractRequestStatus, LogContractTotalMembers, LogContractPhones, LogContractBonificationsVariablesChange, LogContractExpiredBonificationsVariables, LogInvoiceChangeStatus, LogFraudStatusChange, LogReadingChange
from logger.serializers import LogCommitmentDepositMovementSerializer, LogCommunicationChangeSerializer, LogCommunicationProcessStatusChangeSerializer, LogCommunicationStatusChangeSerializer, LogConnectionStatusSerializer, LogConnectionRequestStatusSerializer, LogIncidentStatusChangeSerializer, LogInvoiceDataChangeSerializer, LogOrderStatusSerializer, LogPaymentStatusChangeSerializer, LogSupplyCutStatusSerializer, LogSupplyPointChangeSerializer, LogContractRequestStatusSerializer, LogBailStatusSerializer, LogContractTotalMembersSerializer, LogContractPhonesSerializer, LogContractBonificationsVariablesChangeSerializer, LogContractExpiredBonificationsVariablesSerializer, LogClaimRequestContractChangeSerializer, LogInvoiceChangeStatusSerializer, LogFraudStatusChangeSerializer, LogReadingChangeSerializer
from logger.models import LogBailStatus, LogClaimRequestContractChange, LogCommitmentDepositMovement, LogCommunicationProcessStatusChange, LogCommunicationStatusChange, LogConnectionStatus,LogConnectionRequestStatus, LogIncidentStatusChange, LogInvoiceDataChange, LogOrderStatus, LogPaymentStatusChange, LogSupplyCutStatus, LogSupplyPointChange, LogContractRequestStatus, LogContractTotalMembers, LogContractBonificationsVariablesChange, LogContractExpiredBonificationsVariables, LogInvoiceChangeStatus, LogFraudStatusChange, LogJoinedPaymentStatusChange
from logger.serializers import LogCommitmentDepositMovementSerializer, LogCommunicationProcessStatusChangeSerializer, LogCommunicationStatusChangeSerializer, LogConnectionStatusSerializer, LogConnectionRequestStatusSerializer, LogIncidentStatusChangeSerializer, LogInvoiceDataChangeSerializer, LogOrderStatusSerializer, LogPaymentStatusChangeSerializer, LogSupplyCutStatusSerializer, LogSupplyPointChangeSerializer, LogContractRequestStatusSerializer, LogBailStatusSerializer, LogContractTotalMembersSerializer, LogContractBonificationsVariablesChangeSerializer, LogContractExpiredBonificationsVariablesSerializer, LogClaimRequestContractChangeSerializer, LogInvoiceChangeStatusSerializer, LogFraudStatusChangeSerializer, LogJoinedPaymentStatusChangeSerializer


class LogConnectionStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = LogConnectionStatus.objects.all().order_by('-timestamp')
    serializer_class = LogConnectionStatusSerializer
    permission_classes = [IsAuthenticated]
    

class LogConnectionRequestStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = LogConnectionRequestStatus.objects.all().order_by('-timestamp')
    serializer_class = LogConnectionRequestStatusSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogConnectionRequestStatusFilter
    search_fields = ['object']
    ordering_fields = []
    
class LogSupplyCutStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = LogSupplyCutStatus.objects.select_related(
        'previous_status', 'current_status', 'user'
    ).order_by('-timestamp')
    serializer_class = LogSupplyCutStatusSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogSupplyCutStatusFilter
    search_fields = ['object']
    ordering_fields = []

class LogSupplyPointChangeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = LogSupplyPointChange.objects.all().order_by('-timestamp')
    serializer_class = LogSupplyPointChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogSupplyPointChangeFilter
    search_fields = ['action']
    ordering_fields = []

class LogContractRequestStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = LogContractRequestStatus.objects.all().order_by('-timestamp')
    serializer_class = LogContractRequestStatusSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogContractRequestStatusFilter
    search_fields = ['object']
    ordering_fields = []

class LogOrderStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = LogOrderStatus.objects.all().order_by('-timestamp')
    serializer_class = LogOrderStatusSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogOrderStatusFilter
    search_fields = ['object']
    ordering_fields = []

class LogBailStatusViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows Street to be viewed or edited.
    """
    queryset = LogBailStatus.objects.all().order_by('-timestamp')
    serializer_class = LogBailStatusSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogBailStatusFilter
    search_fields = ['object']
    ordering_fields = []

class LogContractTotalMembersViewSet(viewsets.ModelViewSet):

    queryset = LogContractTotalMembers.objects.all().order_by('-timestamp')
    serializer_class = LogContractTotalMembersSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogContractTotalMembersFilter
    search_fields = ['object']
    ordering_fields = []


class LogContractPhonesViewSet(viewsets.ModelViewSet):
    queryset = LogContractPhones.objects.all().order_by('-timestamp')
    serializer_class = LogContractPhonesSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogContractPhonesFilter
    search_fields = ['object']
    ordering_fields = []

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LogContractBonificationsVariablesChangeViewSet(viewsets.ModelViewSet):
    queryset = LogContractBonificationsVariablesChange.objects.all().order_by('-timestamp')
    serializer_class = LogContractBonificationsVariablesChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogContractBonificationsVariablesChangeFilter
    search_fields = ['object']
    ordering_fields = []
    
class LogContractExpiredBonificationsVariablesViewSet(viewsets.ModelViewSet):
    queryset = LogContractExpiredBonificationsVariables.objects.all().order_by('-timestamp')
    serializer_class = LogContractExpiredBonificationsVariablesSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogContractExpiredBonificationsVariablesFilter
    search_fields = ['object']
    ordering_fields = []

class LogClaimRequestContractChangeViewSet(viewsets.ModelViewSet):
    queryset = LogClaimRequestContractChange.objects.all().order_by('-created_at')
    serializer_class = LogClaimRequestContractChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogClaimRequestContractChangeFilter
    search_fields = ['object']
    ordering_fields = []

class LogInvoiceChangeStatusViewSet(viewsets.ModelViewSet):
    queryset = LogInvoiceChangeStatus.objects.all().order_by('-timestamp')
    serializer_class = LogInvoiceChangeStatusSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogInvoiceChangeStatusFilter
    search_fields = ['object']
    ordering_fields = []

class LogCommitmentDepositMovementViewSet(viewsets.ModelViewSet):
    queryset = LogCommitmentDepositMovement.objects.all().order_by('-timestamp')
    serializer_class = LogCommitmentDepositMovementSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogCommitmentDepositMovementFilter
    search_fields = ['object']
    ordering_fields = []

class LogPaymentStatusChangeViewSet(viewsets.ModelViewSet):
    queryset = LogPaymentStatusChange.objects.all().order_by('-timestamp')
    serializer_class = LogPaymentStatusChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogPaymentStatusChangeFilter
    search_fields = ['object']
    ordering_fields = []

class LogCommunicationChangeViewSet(viewsets.ModelViewSet):
    queryset = LogCommunicationChange.objects.all().order_by('-timestamp')
    serializer_class = LogCommunicationChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogCommunicationChangeFilter
    search_fields = ['object']
    ordering_fields = []

class LogFraudStatusChangeViewSet(viewsets.ModelViewSet):
    queryset = LogFraudStatusChange.objects.all().order_by('-timestamp')
    serializer_class = LogFraudStatusChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogFraudStatusChangeFilter
    search_fields = ['object']
    ordering_fields = []

class LogIncidentStatusChangeViewSet(viewsets.ModelViewSet):
    queryset = LogIncidentStatusChange.objects.all().order_by('-timestamp')
    serializer_class = LogIncidentStatusChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogIncidentStatusChangeFilter
    search_fields = ['object']
    ordering_fields = []
    

class LogCommunicationStatusChangeViewSet(viewsets.ModelViewSet):
    queryset = LogCommunicationStatusChange.objects.all().order_by('-timestamp')
    serializer_class = LogCommunicationStatusChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogCommunicationStatusChangeFilter
    search_fields = ['object']
    ordering_fields = []

class LogCommunicationProcessStatusChangeViewSet(viewsets.ModelViewSet):
    queryset = LogCommunicationProcessStatusChange.objects.all().order_by('-timestamp')
    serializer_class = LogCommunicationProcessStatusChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogCommunicationProcessStatusChangeFilter
    search_fields = ['object']
    ordering_fields = []

class LogInvoiceDataChangeViewSet(viewsets.ModelViewSet):
    queryset = LogInvoiceDataChange.objects.all().order_by('-timestamp')
    serializer_class = LogInvoiceDataChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogInvoiceDataChangeFilter
    search_fields = ['object']
    ordering_fields = []


class LogContractDataChangeViewSet(viewsets.ModelViewSet):
    queryset = ContractDataChange.objects.all().order_by('-created_at')
    serializer_class = LogContractDataChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogContractDataChangeFilter
    search_fields = ['contract__token']
    ordering_fields = []


class LogReadingChangeViewSet(viewsets.ModelViewSet):
    queryset = LogReadingChange.objects.all().order_by('-timestamp')
    serializer_class = LogReadingChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogReadingChangeFilter
    search_fields = ['observation']
    ordering_fields = []

class LogJoinedPaymentStatusChangeViewSet(viewsets.ModelViewSet):
    queryset = LogJoinedPaymentStatusChange.objects.all().order_by('-timestamp')
    serializer_class = LogJoinedPaymentStatusChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogJoinedPaymentStatusChangeFilter
    search_fields = ['object']
    ordering_fields = []

class LogProductChangeViewSet(viewsets.ModelViewSet):
    queryset = LogProductChange.objects.all().order_by('-timestamp')
    serializer_class = LogProductChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogProductChangeFilter
    search_fields = ['object']
    ordering_fields = []


class LogPriceRateChangeViewSet(viewsets.ModelViewSet):
    queryset = LogPriceRateChange.objects.all().order_by('-timestamp')
    serializer_class = LogPriceRateChangeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LogPriceRateChangeFilter
    search_fields = ['object']
    ordering_fields = []

class OVLogsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class OVLogsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = OVLogsPagination

    def get(self, request, log_id=None):
        # 1. Define models to check for OV logs
        logger_models = [m for m in apps.get_app_config('logger').get_models() if m.__name__.startswith('Log')]
        contract_models = [
            apps.get_model('contract', 'ContractLog'),
            apps.get_model('contract', 'ContractObservation'),
            apps.get_model('contract', 'ContractDataChange')
        ]
        # Add Reading model to track readings from OV
        billing_models = [
            apps.get_model('billing', 'Reading')
        ]
        
        all_models = logger_models + contract_models + billing_models
        
        # Handle single log detail request
        if log_id:
            try:
                # Format is "ModelName_ID"
                if '_' not in log_id:
                    return Response({"detail": "Invalid ID format"}, status=400)
                    
                m_type, m_id = log_id.rsplit('_', 1)
                
                # Find the model class
                model_class = next((m for m in all_models if m.__name__ == m_type), None)
                if not model_class:
                    return Response({"detail": f"Model {m_type} not found"}, status=404)
                    
                obj = model_class.objects.filter(id=m_id).first()
                if not obj:
                    return Response({"detail": "Entry not found"}, status=404)
                
                # Extract detail using the same logic as listing
                detail = self._get_obj_detail(obj, m_type)
                
                # Find timestamp
                ts = None
                for ts_field in ['timestamp', 'created_at', 'requested_at', 'reading_date']:
                    if hasattr(obj, ts_field):
                        ts = getattr(obj, ts_field)
                        break
                        
                return Response({
                    "id": log_id,
                    "type": m_type,
                    "app": obj._meta.app_label,
                    "timestamp": ts,
                    "detail": detail,
                    "user_id": getattr(obj, 'user_id', None),
                    "user_name": obj.user.username if hasattr(obj, 'user') and obj.user else "System"
                })
            except Exception as e:
                return Response({"detail": str(e)}, status=500)

        # Handle list request
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        search_query = request.query_params.get('search')
        
        queries = []
        for m in all_models:
            qs = m.objects.all()
            
            # Identify how to filter this model for OV-related records
            has_user = hasattr(m, 'user')
            
            from django.db.models import Q
            
            if m.__name__ == 'Reading':
                # Readings from OV are marked with origin='OV'
                qs = qs.filter(origin='OV')
            elif m.__name__ == 'ContractObservation':
                # Observations by OV user OR containing specific text
                qs = qs.filter(Q(user__groups__name__in=['ov', 'OV']) | Q(observation__icontains='Oficina Virtual'))
            elif has_user:
                # General case for logs with a user field
                qs = qs.filter(user__groups__name__in=['ov', 'OV'])
            else:
                # Skip models that we don't know how to filter for OV and don't have a user
                continue
            
            # Extract common fields for union
            if hasattr(m, 'timestamp'):
                ts_field = 'timestamp'
            elif hasattr(m, 'created_at'):
                ts_field = 'created_at'
            elif hasattr(m, 'requested_at'): 
                ts_field = 'requested_at'
            elif hasattr(m, 'reading_date'): # Reading uses reading_date
                ts_field = 'reading_date'
            else:
                continue
                
            # Date filters
            if start_date:
                qs = qs.filter(**{f"{ts_field}__date__gte": start_date})
            if end_date:
                qs = qs.filter(**{f"{ts_field}__date__lte": end_date})
                
            # Search filter
            if search_query:
                import django.db.models as django_models
                search_q = Q()
                for field in m._meta.fields:
                    if isinstance(field, (django_models.CharField, django_models.TextField)):
                        search_q |= Q(**{f"{field.name}__icontains": search_query})
                
                if has_user:
                    search_q |= Q(user__username__icontains=search_query)
                    search_q |= Q(user__email__icontains=search_query)
                    
                qs = qs.filter(search_q)
                
            qs = qs.annotate(
                model_type=Value(m.__name__, output_field=CharField(max_length=100)),
                model_app=Value(m._meta.app_label, output_field=CharField(max_length=100)),
                unified_timestamp=F(ts_field)
            ).values('id', 'unified_timestamp', 'model_type', 'model_app')
            
            queries.append(qs)
        
        if not queries:
            return Response({"count": 0, "results": []})
            
        combined_qs = queries[0].union(*queries[1:]).order_by('-unified_timestamp')
        
        paginator = self.pagination_class()
        try:
            page = paginator.paginate_queryset(combined_qs, request, view=self)
        except Exception:
            combined_list = list(combined_qs)
            page = paginator.paginate_queryset(combined_list, request, view=self)
            
        items = page if page is not None else combined_qs
            
        # Group IDs by (app, model) type for efficient fetching
        model_id_map = {}
        for item in items:
            key = (item['model_app'], item['model_type'])
            m_id = item['id']
            if key not in model_id_map:
                model_id_map[key] = []
            model_id_map[key].append(m_id)
            
        # Fetch the complete objects
        fetched_objects = {}
        for (app_label, m_type), ids in model_id_map.items():
            model_class = apps.get_model(app_label, m_type)
            # Use select_related where appropriate
            qs = model_class.objects.all()
            if hasattr(model_class, 'user'):
                qs = qs.select_related('user')
            
            objs = qs.in_bulk(ids)
            for m_id, obj in objs.items():
                fetched_objects[(app_label, m_type, m_id)] = obj
                
        # Format the uniform results list
        results = []
        for item in items:
            app_label = item['model_app']
            m_type = item['model_type']
            m_id = item['id']
            obj = fetched_objects.get((app_label, m_type, m_id))
            if not obj:
                continue
                
            detail = self._get_obj_detail(obj, m_type)
                        
            results.append({
                "id": f"{m_type}_{m_id}",
                "type": m_type,
                "app": app_label,
                "timestamp": item['unified_timestamp'],
                "detail": detail,
                "user_id": getattr(obj, 'user_id', None),
                "user_name": obj.user.username if hasattr(obj, 'user') and obj.user else "System"
            })
            
        if page is not None:
            return paginator.get_paginated_response(results)
        return Response(results)

    def _get_obj_detail(self, obj, m_type):
        """Helper to extract relevant details based on model type."""
        detail = {}
        exclude_fields = ['id', 'user', 'token', 'model_type', 'model_app', 'unified_timestamp']
        
        for field in obj._meta.fields:
            if field.name not in exclude_fields:
                val = getattr(obj, field.name)
                if val is not None and not isinstance(val, (int, float, bool, str)):
                    detail[field.name] = str(val)
                else:
                    detail[field.name] = val
                    
        # Check if we can extract contract_id explicitly to help frontend
        if hasattr(obj, 'contract') and obj.contract:
            detail['contract_id'] = obj.contract.id
        elif hasattr(obj, 'invoice') and obj.invoice and obj.invoice.contract:
            detail['contract_id'] = obj.invoice.contract.id
        
        # Special handling for Readings
        if m_type == 'Reading':
            detail['contract'] = str(obj.contract) if obj.contract else None
            detail['meter'] = str(obj.meter) if obj.meter else None
            detail['value'] = float(obj.reading_value) if obj.reading_value else 0
            
        return detail