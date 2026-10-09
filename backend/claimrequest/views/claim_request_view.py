import csv
import datetime
import io

from django.forms.utils import ValidationError
from rest_framework import viewsets, status, views
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Count, Max, Sum, F, Q
from rest_framework.decorators import action
from django.utils.translation import gettext as _
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.views import APIView

from auth.permissions import PermissionManager
from ..filter.claim_request_filter import ClaimRequestFilter
from ..models import ClaimRequest, ClaimRequestPayment, ClaimRequestStep, Contract
from ..serializers.claim_request_serializer import ClaimRequestSerializer
from ..serializers.claim_request_list_serializer import ClaimRequestListSerializer
from ..serializers.claim_request_save_serializer import ClaimRequestSaveSerializer
from ..serializers.claim_request_payment_serializer import ContractWithClaimPaymentsSerializer
from claimrequest.tasks import generate_claim_expenses

class ClaimRequestViewSet(viewsets.ModelViewSet):
  queryset = ClaimRequest.objects.all().order_by('-created_at','due_date', 'status')
  serializer_class = ClaimRequestSerializer
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  filterset_class = ClaimRequestFilter
  
  # Especifiquem els camps que es poden ordenar
  ordering_fields = [
      'id', 'created_at', 'updated_at', 'token', 'due_date',
      'status__name', 'current_step__name'
  ]
  
  # Especifiquem els camps on es pot cercar
  search_fields = [
      'token', 'description',
      'status__name', 'current_step__name', 'current_step__token',
      'payments__token'
  ]
  
  def get_queryset(self):
    queryset = super().get_queryset()
    
    if self.action in ['list', 'retrieve']:
        # Anotem el total de pagaments i contractes, i la suma dels amounts
        queryset = queryset.annotate(
            total_payments=Count('payments', distinct=True),
            total_contracts=Count('payments__contract', distinct=True),
            amount=Sum('payments__payment__amount', filter=Q(payments__is_excluded=False))
        ).select_related(
            'status',
            'current_step'
        ).prefetch_related(
            'payments',
            'payments__payment',
            'payments__contract'
        )

    # Relax visibility: show all claim requests (filtering is handled via permissions)
    return queryset
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return ClaimRequestListSerializer
        elif self.action == 'retrieve':
            return ClaimRequestSerializer
    return ClaimRequestSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context


  @action(detail=False, methods=['post'], url_path='get-contracts-claim-request')
  def get_contracts_claim_request(self, request):
    claim_request_id = request.data.get('claim_request_id')
    if not claim_request_id:
        raise ValidationError("Claim request id is required")

    file = request.data.get('file', None)
    contracts = []
    if file:
        decoded_file = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded_file), delimiter=';')
        contract_tokens = []
        for row in reader:
            contract = row.get(_("Contracte"))
            if contract is not None:
                contract_tokens.append(contract)
        contracts = Contract.objects.filter(
            token__in=contract_tokens,
            claim_requests__claim_request__id=claim_request_id
        ).distinct()
    else:
        minPendingPayments = request.data.get("min_pending_payments", None)
        maxPendingPayments = request.data.get("max_pending_payments", None)
        minPreviousVulnRequest = request.data.get("min_previous_vuln_request", None)
        maxPreviousVulnRequest = request.data.get("max_previous_vuln_request", None)
        minPendingImport = request.data.get("min_pending_import", None)
        maxPendingImport = request.data.get("max_pending_import", None)
        useTypes = request.data.get("use_types", None)
        contractStatuses = request.data.get("contract_statuses", None)

        claim_request_payment_q = Q(claim_requests__claim_request__id=claim_request_id)
        contracts = Contract.objects.filter(claim_request_payment_q).annotate(
            pending_payments_count=Count(
                'claim_requests',
                filter=claim_request_payment_q,
            ),
            pending_payments_amount=Sum(
                'claim_requests__payment__amount',
                filter=claim_request_payment_q,
            ),
            last_vulnerability_request_date=Max(
                'vulnerability_requests__request_at',
                filter=claim_request_payment_q,
            ),
        ).distinct()

        if minPendingPayments is not None and minPendingPayments != "":
            contracts = contracts.filter(pending_payments_count__gte=int(minPendingPayments))
        if maxPendingPayments is not None and maxPendingPayments != "" and maxPendingPayments > 0:
            contracts = contracts.filter(pending_payments_count__lte=int(maxPendingPayments))
        if minPreviousVulnRequest is not None and minPreviousVulnRequest != "":
            contracts = contracts.filter(last_vulnerability_request_date__gte=datetime.datetime.now() - datetime.timedelta(days=int(minPreviousVulnRequest)))
        if maxPreviousVulnRequest is not None and maxPreviousVulnRequest != "":
            contracts = contracts.filter(last_vulnerability_request_date__lte=datetime.datetime.now() - datetime.timedelta(days=int(maxPreviousVulnRequest)))
        if minPendingImport is not None and minPendingImport != "":
            contracts = contracts.filter(pending_payments_amount__gte=float(minPendingImport))
        if maxPendingImport is not None and maxPendingImport != "" and maxPendingImport > 0:
            contracts = contracts.filter(pending_payments_amount__lte=float(maxPendingImport))
        if useTypes is not None and len(useTypes) > 0:
            contracts = contracts.filter(use_type__id__in=useTypes)
        if contractStatuses is not None and len(contractStatuses) > 0:
            contracts = contracts.filter(status__id__in=contractStatuses)

    # contracts = ContractWithClaimPaymentsSerializer(contracts, many=True).data
    contract_ids = contracts.values_list('id', flat=True)
    return Response({"contract_ids": contract_ids}, status=status.HTTP_200_OK)

  @action(detail=False, methods=['post'], url_path='generate-expenses')
  def generate_expenses(self, request):
      
    """ 
        claim_request_id: props.request.id,
        claim_request_step_id: props.step.id,
        contract_ids: [...selectedContracts.value],
        price_rate_ids: availablePriceRates.value.map(priceRate => priceRate.id),
    """
    claim_request_id = request.data.get('claim_request_id')
    claim_request_step_id = request.data.get('claim_request_step_id')
    contract_ids = request.data.get('contract_ids')
    price_rate_ids = request.data.get('price_rate_ids')
    if not claim_request_step_id or not contract_ids or len(contract_ids) == 0 or not price_rate_ids or len(price_rate_ids) == 0:
        raise Exception("Invalid request data")
    
    try:
        claim_request_step = ClaimRequestStep.objects.get(id=claim_request_step_id)
    except ClaimRequest.DoesNotExist:
        raise Exception("Claim request step not found")
    
    task = generate_claim_expenses.delay(claim_request_id, claim_request_step_id, contract_ids, price_rate_ids)
    claim_request_step.task_id = task.id
    claim_request_step.save()
    
    return Response({"task_id": task.id}, status=status.HTTP_200_OK)
    
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()
  
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
        group_permissions = PermissionManager.get_model_group_permissions(group, 'claimrequest')
        return Response(group_permissions, status=status.HTTP_200_OK)
    permissions = PermissionManager.get_model_permissions(request.user, 'claimrequest', 'claimrequest')
    return Response(permissions, status=status.HTTP_200_OK)
    
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()

# Vista per obtenir els contractes d'una reclamació
# Permet filtrar per is_juridic

class ClaimRequestContractsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ClaimRequest.objects.all().order_by('-created_at')
    lookup_field = 'id'
    
    def retrieve(self, request, id=None):
        try:
            claim_request = ClaimRequest.objects.get(id=id)
            
            # Obtenim el paràmetre is_juridic del query string
            is_juridic = request.query_params.get('is_juridic')
            step_id = request.query_params.get('step', None)
            
            # Obtenim els contractes únics dels pagaments de la reclamació
            contracts_query = Contract.objects.filter(
                claim_requests__claim_request=claim_request
            ).distinct()
            
            # Si hi ha filtre per is_juridic, l'apliquem
            if is_juridic is not None:
                is_juridic_bool = is_juridic.lower() == 'true'
                contracts_query = contracts_query.filter(holder__is_juridic=is_juridic_bool)
            
            contracts = list(contracts_query)
            
            serializer = ContractWithClaimPaymentsSerializer(
                contracts, 
                many=True, 
                context={'request': request, 'claim_request_id': id, 'step_id': step_id}
            )
            
            # Calculem els comptadors
            count_excluded = sum(1 for contract in contracts if all(
                payment.is_excluded 
                for payment in contract.claim_requests.filter(claim_request_id=id)
            ))
            
            return Response({
                'count': len(contracts),
                'count_excluded': count_excluded,
                'results': serializer.data
            })
            
        except ClaimRequest.DoesNotExist:
            return Response(
                {"error": "La reclamació no existeix"},
                status=status.HTTP_404_NOT_FOUND
            )

class MarkContractsVulnerableSerializer(serializers.Serializer):
    request_id = serializers.IntegerField(required=True)
    contract_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )

class MarkContractsVulnerableViewSet(views.APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ClaimRequest.objects.all().order_by('-created_at')
    def get(self, request, *args, **kwargs):
        return Response({"message": "Aquesta vista només accepta mètodes POST"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request, *args, **kwargs):
        serializer = MarkContractsVulnerableSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        request_id = serializer.validated_data['request_id']
        contract_ids = serializer.validated_data['contract_ids']
        
        try:
            claim_request = ClaimRequest.objects.get(id=request_id)
            
            # Obtenim els ClaimRequestPayment que tenen els contractes especificats
            claim_payments = ClaimRequestPayment.objects.filter(
                claim_request=claim_request,
                contract__id__in=contract_ids
            )
            
            # Actualitzem el camp is_vulnerable a True
            updated_count = claim_payments.update(is_vulnerable=True)
            
            return Response({
                "message": f"S'han marcat {updated_count} contractes com a vulnerables",
                "updated_count": updated_count
            })
            
        except ClaimRequest.DoesNotExist:
            return Response(
                {"error": "La reclamació no existeix"},
                status=status.HTTP_404_NOT_FOUND
            )
            