from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.contrib.auth.models import Group

from auth.permissions import PermissionManager
from billing.filter.commitment_deposit_filter import CommitmentDepositFilter
from billing.models import CommitmentDeposit, PaymentStatus, Payment
from coredata.models import ConfigProject
from billing.serializers.commitment_deposit_serializer import CommitmentDepositSerializer, CommitmentDepositListSerializer, CommitmentDepositSaveSerializer
from billing.permissions import CommitmentDepositPermission
from contract.models import PiggyBankMovement, PiggyBank
from coredata.utils.name_utils import generate_token
from django.utils import timezone

class CommitmentDepositViewSet(viewsets.ModelViewSet):
  queryset = CommitmentDeposit.objects.all().order_by('-created_at')
  serializer_class = CommitmentDepositSerializer
  permission_classes = [IsAuthenticated, CommitmentDepositPermission]
  filterset_class = CommitmentDepositFilter
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  search_fields = [
      'token', 'invoices__token', 'customer_final', 
      'customer_token_final', 'contract__token', 'contract__holder__token', 
      'contract__holder__name']
  ordering_fields = '__all__'
  
  def get_serializer_class(self):
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return CommitmentDepositListSerializer
        elif self.action == 'retrieve':
            return CommitmentDepositSerializer
    return CommitmentDepositSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=True, methods=['put'], url_path='liquidate-all')
  def liquidate_all(self, request, pk=None):
    commitment_deposit = self.get_object()
    status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
    invoices = commitment_deposit.invoices.all()
    payments = Payment.objects.filter(invoice__in=invoices).exclude(status=status_paid)
    for payment in payments:
        payment.status = status_paid
        payment.save()
    return Response(status=status.HTTP_200_OK)
  
  @action(detail=True, methods=['put'], url_path='save-balance')
  def save_balance(self, request, pk=None):
    commitment_deposit = self.get_object()
    try:
        remaining_to_share = commitment_deposit.remaining_to_share
        contract = commitment_deposit.contract
        piggy_bank = contract.piggy_bank if contract else None

        if remaining_to_share > 0 and piggy_bank:
            PiggyBankMovement.objects.create(
                token=generate_token(PiggyBankMovement),
                piggy_bank=piggy_bank,
                amount=remaining_to_share,
                is_positive=True,
                movement_date=timezone.now(),
                commitment_deposit=commitment_deposit,
            )
            piggy_bank.amount += remaining_to_share
            piggy_bank.save()
            commitment_deposit.remaining_to_share = 0
            commitment_deposit.save()
    except: 
        return Response(status=status.HTTP_400_BAD_REQUEST)
    
    return Response(status=status.HTTP_200_OK)
  
  @action(detail=False, methods=['get'], url_path='permissions')
  def permissions(self, request):
      pk = request.query_params.get('id')
      if pk:
          user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
          if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
              return Response( None, status=status.HTTP_403_FORBIDDEN )
          group = Group.objects.filter(id=pk).first()
          if not group:
              return Response( None, status=status.HTTP_404_NOT_FOUND )
          group_permissions = PermissionManager.get_model_group_permissions(group, 'commitmentdeposit')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'commitmentdeposit', 'billing')
      return Response(permissions, status=status.HTTP_200_OK)
    
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()