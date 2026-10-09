from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.decorators import action
from billing.filter.payment_commitment_filter import PaymentCommitmentFilter
from billing.models import CommitmentDepositStatus, Payment, PaymentCommitment, PaymentCommitmentStatus, PaymentStatus, PaymentType
from billing.serializers.payment_commitment_serializer import (
    PaymentCommitmentSerializer,
    PaymentCommitmentSaveSerializer
)
from billing.permissions import CommitmentDepositPermission
from billing.utils.invoice_service import generate_payment_id
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from coredata.models import ConfigProject, PersonBank
from service.models import CompanyBank
from logger.models import LogCommitmentDepositMovement
from billing.utils.payment_service import log_payment_status, generate_payment_movement
from django.db import transaction
from billing.utils.commitment_deposit_service import add_wallet_payment

class PaymentCommitmentViewSet(viewsets.ModelViewSet):
  queryset = PaymentCommitment.objects.all().order_by('due_date')
  serializer_class = PaymentCommitmentSerializer
  permission_classes = [IsAuthenticated, CommitmentDepositPermission]
  filterset_class = PaymentCommitmentFilter
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  search_fields = '__all__'
  ordering_fields = '__all__'
  
  def get_serializer_class(self):
    if self.request.method in ['GET']:
      return PaymentCommitmentSerializer
    return PaymentCommitmentSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=False, methods=['post'], url_path='return')
  def return_payment(self, request):
      payment_id = request.query_params.get('payment_id')
      user = request.user if request.user else None
      if not payment_id:
          return Response(
              {"detail": "Missing required fields: 'payment_id'."},
              status=status.HTTP_400_BAD_REQUEST
          )
      disconnect_payment_signals()
      payment = Payment.objects.get(id=payment_id)
      now = timezone.now()
      payment_status_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
      log_payment_status(
        payment,
        payment_status_returned,
        user,
        now
      )
      generate_payment_movement(
        payment,
        payment_status_returned,
        now,
        payment.payment_type_token,
        payment.payment_bank,
        user,
        None,
        payment.remittances.filter(sent_at__isnull=False).order_by('-sent_at').first()
      )
      
      payment.status = payment_status_returned
      payment.save()
      
      deposit_paid = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value)
      deposit_partially_paid = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_partially_paid_token').value)
      pay_comm_paid = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_paid_token').value)
      pay_comm_pending = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_pending_token').value)
      pay_comm_confirmed = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_confirmed_token').value)
      
      commitment_deposit = payment.commitment_deposit
      print("commitment_deposit")
      print(commitment_deposit)
      
      LogCommitmentDepositMovement.objects.create(
        timestamp=now,
        object=commitment_deposit,
        previous_remaining=commitment_deposit.remaining,
        current_remaining=commitment_deposit.remaining + payment.amount,
      )
      
      if commitment_deposit.status == deposit_paid:
        commitment_deposit.status = deposit_partially_paid
      commitment_deposit.remaining += payment.amount
      if commitment_deposit.remaining_to_share > 0:
        commitment_deposit.remaining_to_share -= payment.amount
      
      # Get the PaymentType object from the payment_type_token
      payment_type_obj = None
      if payment.payment_type_token:
        payment_type_obj = PaymentType.objects.filter(token=payment.payment_type_token).first()
      
      try:
        payment_to_return = PaymentCommitment.objects.filter(
          commitment_deposit=commitment_deposit,
          is_guide=True,
          amount=payment.amount,
          status=pay_comm_paid
        ).order_by('due_date').first()
        if payment_to_return:
          payment_to_return.status = pay_comm_confirmed
          payment_to_return.currently_paid = 0
          payment_to_return.save()
        else:
          PaymentCommitment.objects.create(
            token=f"{commitment_deposit.token}{PaymentCommitment.objects.filter(commitment_deposit=commitment_deposit).count() + 1}",
            commitment_deposit=commitment_deposit,
            is_guide=True,
            amount=payment.amount,
            status=pay_comm_pending,
            due_date=payment.due_date,
          )
      except PaymentCommitment.DoesNotExist as e:
        PaymentCommitment.objects.create(
          token=f"{commitment_deposit.token}{PaymentCommitment.objects.filter(commitment_deposit=commitment_deposit).count() + 1}",
          commitment_deposit=commitment_deposit,
          is_guide=True,
          amount=payment.amount,
          status=pay_comm_pending,
          due_date=payment.due_date,
        )
      except Exception as e:
          return Response(
            {"detail": "Error returning payment: " + str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
          )
      print("here")
      PaymentCommitment.objects.create(
        commitment_deposit=commitment_deposit,
        payment_type=payment_type_obj,
        is_guide=False,
        currently_paid=payment.amount * -1,
        payment_date=payment.payment_date,
      )
     
      
      commitment_deposit.save()
      reconnect_payment_signals()
      return Response({"ok": "ok"}, status=status.HTTP_200_OK)

  @action(detail=False, methods=['post'], url_path='bulk-save')
  def bulk_save(self, request):
      data = request.data
      payment_type_id = data.get('payment_type_id')
      payment_bank_id = data.get('payment_bank')
      company_bank_id = data.get('company_iban') or data.get('company_bank')
      payment_bank_final = data.get('payment_bank_final')
      payment_swift_final = data.get('payment_swift_final')
      payments_list = data.get('payments', [])
      
      user = request.user if request.user else None
      
      payment_type = None
      if payment_type_id:
          payment_type = PaymentType.objects.filter(id=payment_type_id).first()
          
      payment_bank = None
      if payment_bank_id:
          payment_bank = PersonBank.objects.filter(id=payment_bank_id).first()

      company_bank = None
      if company_bank_id:
          company_bank = CompanyBank.objects.filter(id=company_bank_id).first()

      with transaction.atomic():
          for p_data in payments_list:
              commitment_id = p_data.get('id')
              wallet_payment_date = p_data.get('wallet_payment_date')
              
              if not commitment_id:
                  continue
                  
              instance = PaymentCommitment.objects.get(id=commitment_id)
              
              # Check if the commitment is still eligible for payment (not paid or cancelled)
              paid_token = ConfigProject.objects.get(token='payment_commitment_status_paid_token').value
              cancelled_token = ConfigProject.objects.get(token='payment_commitment_status_cancelled_token').value
              
              if instance.status.token in [paid_token, cancelled_token]:
                  continue
                  
              if payment_type:
                  instance.payment_type = payment_type
              if payment_bank:
                  instance.payment_bank = payment_bank
              if payment_bank_final:
                  instance.payment_bank_final = payment_bank_final
              if payment_swift_final:
                  instance.payment_swift_final = payment_swift_final
              
              p_comp_bank_id = p_data.get('company_iban') or p_data.get('company_bank')
              p_comp_bank = CompanyBank.objects.filter(id=p_comp_bank_id).first() if p_comp_bank_id else company_bank
              
              if p_comp_bank:
                  if p_comp_bank.iban:
                      instance.payment_bank_final = p_comp_bank.iban
                  if p_comp_bank.swift:
                      instance.payment_swift_final = p_comp_bank.swift

              instance.save()
              
              # Transition to "Confirmed" status
              try:
                  confirmed_status_token = ConfigProject.objects.get(token='payment_commitment_status_confirmed_token').value
                  confirmed_status = PaymentCommitmentStatus.objects.get(token=confirmed_status_token)
                  instance.status = confirmed_status
              except (ConfigProject.DoesNotExist, PaymentCommitmentStatus.DoesNotExist):
                  # Fallback: keep current status if 'Confirmed' is not configured yet
                  pass
              
              instance.save()
              
              # Call the service to create the Payment object
              # add_wallet_payment now has locking and uniqueness checks
              new_payment = add_wallet_payment(instance, user, False, wallet_payment_date, p_comp_bank)
              
              # Log the movement
              logger_data = {
                  'object': instance.commitment_deposit,
                  'previous_status': instance.commitment_deposit.status,
                  'current_status': instance.commitment_deposit.status,
                  'previous_remaining': instance.commitment_deposit.remaining,
                  'current_remaining': instance.commitment_deposit.remaining,
                  'new_wallet': new_payment,
                  'user': user,
              }
              LogCommitmentDepositMovement.objects.create(**logger_data)
              
      return Response({"ok": "ok"}, status=status.HTTP_200_OK)