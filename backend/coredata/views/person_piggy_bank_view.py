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
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
import datetime
from coredata.models import ConfigProject, PersonPiggyBank, PersonAddress, PersonBank, PersonPiggyBankMovement
from contract.models import (PaymentType)
from coredata.serializers import PersonPiggyBankSerializer
from coredata.utils.name_utils import generate_token
from billing.utils.payment_service import generate_payment_movement
from coredata.permissions import PersonPermission
class PersonPiggyBankViewSet(viewsets.ModelViewSet):
    queryset = PersonPiggyBank.objects.all().order_by('-amount')
    serializer_class = PersonPiggyBankSerializer
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    
    @action(detail=True, methods=['put'], url_path='return-money')
    def return_person_piggy_bank_money(self, request, pk=None):
        person_piggy_bank = self.get_object()
        
        payment_type_id = request.data.get('payment_type_id', None)
        payment_date = request.data.get('payment_date', None)
        bank_debit_id = request.data.get('bank_debit_id', None)
        return_date = request.data.get('return_date', None)
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
            person = person_piggy_bank.person.first()
            address_final = person.addresses.filter(is_billing=True).first()
            if not address_final:
                address_final = person.addresses.first()
        except:
            person = None
            address_final = None
        
        if bank_debit:
            payer_final = f"{bank_debit.name}"
            payer_token_final = bank_debit.dni
        else:
            payer_final = f"{person.name}{' ' + person.surname if person.surname else ''}"
            payer_token_final = person.token
        name_translated = _("RETURN BALANCE")
        
        new_payment = Payment.objects.create(
            token=generate_payment_id('04'),
            name=name_translated,
            status=PaymentStatus.objects.get(is_default=True),
            person=person,
            amount=float(amount),
            due_date=return_date,
            payment_type=payment_type.name,
            payment_type_token=payment_type.token,
            payment_date=return_date,
            payment_bank=bank_debit.iban if bank_debit and bank_debit.iban else None,
            payment_swift=bank_debit.swift if bank_debit and bank_debit.swift else None,
            customer_final=f"{person.name}{' ' + person.surname if person.surname else ''}",
            customer_token_final=person.token,
            payer_final=payer_final,
            payer_token_final=payer_token_final,
            address_final=f"{address_final.address.street} {address_final.address.street_number}" if address_final and address_final.address else "-",
            location_final=f"{address_final.address.postal_code} {address_final.address.city}, {address_final.address.province} - {address_final.address.country}" if address_final and address_final.address else "-",
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
        
        PersonPiggyBankMovement.objects.create(
            token=generate_token(PersonPiggyBankMovement),
            person_piggy_bank=person_piggy_bank,
            amount=amount,
            payment=new_payment,
            is_positive=False,
            movement_date=return_date,
            user=user,
        )
        if not bank_debit or mark_as_paid:
            new_payment.status = paid_status
            new_payment.save()
        
        
        person_piggy_bank.amount -= Decimal(amount)
        person_piggy_bank.save()
        return Response({'message': 'Piggy bank money returned successfully'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='permissions')
    def permissions(self, request):
        return Response({
            'can_view': request.user.has_perm('coredata.view_personpiggybank'),
            'can_change': request.user.has_perm('coredata.change_personpiggybank'),
        }, status=status.HTTP_200_OK)

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()