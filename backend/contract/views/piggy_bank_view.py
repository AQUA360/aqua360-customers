from datetime import timedelta
from decimal import Decimal
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from billing.models import Payment, PaymentStatus
from billing.utils.invoice_service import generate_payment_id
from contract.serializers.piggy_bank_serializer import PiggyBankSerializer
from contract.permissions import ContractPermission
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
import datetime
from coredata.models import ConfigProject
from contract.models import (Contract, PaymentType, PiggyBank, PiggyBankMovement)
from coredata.models import PersonAddress, PersonBank
from coredata.utils.name_utils import generate_token
from billing.utils.payment_service import generate_payment_movement
from django.utils.translation import gettext as _
class PiggyBankViewSet(viewsets.ModelViewSet):
    queryset = PiggyBank.objects.all().order_by('-amount')
    serializer_class = PiggyBankSerializer
    permission_classes = [IsAuthenticated, ContractPermission]
    #filterset_class = PiggyBankFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    
    @action(detail=True, methods=['put'], url_path='return-money')
    def return_piggy_bank_money(self, request, pk=None):
        piggy_bank = self.get_object()
        
        payment_type_id = request.data.get('payment_type_id', None)
        payment_date = request.data.get('payment_date', None)
        bank_debit_id = request.data.get('bank_debit_id', None)
        return_date = request.data.get('return_date', None)
        mark_as_paid = request.data.get('mark_as_paid', True)
        amount = request.data.get('amount', 0)
        user = self.request.user

        paid_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
        pending_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
        
        payment_type = PaymentType.objects.get(id=payment_type_id)
        if bank_debit_id and payment_type.token == "BANK_TRANSFER":
            bank_debit = PersonBank.objects.get(id=bank_debit_id)
        else:
            bank_debit = None
        
        return_date = datetime.datetime.strptime(return_date, '%Y-%m-%d').date()
        
        try:
            contract = Contract.objects.get(piggy_bank=piggy_bank)
            address_final = contract.address_billing.address
        except:
            contract = None
            found_address = PersonAddress.objects.filter(person=piggy_bank.person, is_billing=True).first()
            if found_address:
                address_final = found_address.address
            else:
                address_final = None
        
        if contract.payment and contract.payment.IBAN:
            payer_final = f"{contract.payment.IBAN.name}"
            payer_token_final = contract.payment.IBAN.dni
        else:
            payer_final = f"{contract.holder.name} {contract.holder.surname}"
            payer_token_final = contract.holder.token
        
        new_payment = Payment.objects.create(
            token=generate_payment_id('04'),
            name=f"{_('RETURN BALANCE')} {contract.token}",
            status=PaymentStatus.objects.get(is_default=True),
            contract=contract,
            amount=float(amount),
            due_date=return_date,
            payment_type=payment_type.name,
            payment_type_token=payment_type.token,
            payment_date=return_date,
            payment_bank=bank_debit.iban if bank_debit and bank_debit.iban else None,
            payment_swift=bank_debit.swift if bank_debit and bank_debit.swift else None,
            customer_final=f"{contract.holder.name} {contract.holder.surname}" if contract else f"{piggy_bank.person.name} {piggy_bank.person.surname}",
            customer_token_final=contract.holder.token if contract else piggy_bank.person.token,
            payer_final=payer_final,
            payer_token_final=payer_token_final,
            address_final=f"{address_final.street} {address_final.street_number}" if address_final else "-",
            location_final=f"{address_final.postal_code} {address_final.city}, {address_final.province} - {address_final.country}" if address_final else "-",
        )
        new_payment.status = pending_status
        if not bank_debit or mark_as_paid:
            generate_payment_movement(
                new_payment,
                paid_status,
                return_date,
                payment_type.token,
                bank_debit.iban if bank_debit and bank_debit.iban else None,
                user,
                add_bank=True,
            )
        
        PiggyBankMovement.objects.create(
            token=generate_token(PiggyBankMovement),
            piggy_bank=piggy_bank,
            amount=amount,
            payment=new_payment,
            is_positive=False,
            movement_date=return_date,
            user=user,
        )
        
        if not bank_debit or mark_as_paid:
            new_payment.status = paid_status
            new_payment.save()
        
        
        piggy_bank.amount -= Decimal(amount)
        piggy_bank.save()
        return Response({'message': 'Piggy bank money returned successfully'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        return Response({
            'can_view': request.user.has_perm('contract.view_piggybank'),
            'can_change': request.user.has_perm('contract.change_piggybank'),
        }, status=status.HTTP_200_OK)

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()