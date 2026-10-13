from django.utils import timezone
from rest_framework.decorators import action

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework import viewsets, status
from rest_framework.response import Response

from auth.permissions import PermissionManager
from billing.models import InvoiceStatus, Payment, PaymentStatus
from billing.utils.confirm_invoice_service import confirm_invoice
from billing.utils.payment_service import generate_payment_movement, log_payment_status
from contract.utils.bail_service import check_unpaid_invoices
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token


from ..filters import BailFilter

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db.models import Q

from contract.models import (Bail, BailStatus, Contract, PiggyBankMovement)
from contract.models import (Bail)
from contract.serializers.bail_serializer import (BailSerializer, BailListSerializer)

from logger.models import LogBailStatus
from django.contrib.auth.models import Group

class BailViewSet(viewsets.ModelViewSet):
    queryset = Bail.objects.all().order_by('-status', 'payment_date')
    serializer_class = BailSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filterset_class = BailFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = ['token', 'contract__token', 'contract__holder',
                     'product__name', 'product__token']
    ordering_fields = ['token', 'amount', 'payment_date', 'created_at', 'contract__status']
    
    def get_serializer_class(self):
        if self.action == 'list':  # Corresponds to GET / (list view)
            return BailListSerializer
        elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
            return BailSerializer
        return super().get_serializer_class()

        
    @action(detail=False, methods=['post'], url_path='liquidate')
    def liquidate_bail(self, request):
        """ 
        # used for testing purposes
        payments_unpaid = Payment.objects.exclude(status__token__in=['-6','5','0'])
        for payment in payments_unpaid:
            payment.status = PaymentStatus.objects.get(token="-1")
            payment.save() """
            
        user = request.user
        
        bail_ids = request.data.get('bail_ids', [])
        bail_status_returned_token = ConfigProject.objects.get(token='bail_status_returned_token').value
        returned_status = BailStatus.objects.get(token=bail_status_returned_token)
        status_invoice_confirmed = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)
        payment_status_piggy = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_piggy_token').value)
        contracts = Contract.objects.filter(bails__id__in=bail_ids)
        bails = Bail.objects.filter(contract__in=contracts)
        bails.update(status=returned_status, return_date=timezone.now(), payment_date=timezone.now())
        for bail in bails:
            invoice = bail.invoice
            if invoice:
                invoice.status = status_invoice_confirmed
                invoice.save()
                confirm_invoice(invoice)
            
            invoice_payments = Payment.objects.filter(invoice=invoice)
            for payment in invoice_payments:
                log_payment_status(
                    payment, payment_status_piggy, user
                )
                
                generate_payment_movement(
                    payment, payment_status_piggy, 
                    payment.payment_date, "BALANCE", 
                    None, user,
                    None, 
                    None
                    )
                payment.status = payment_status_piggy
                payment.save()
                payment.refresh_from_db()
            
            piggy_bank_movement = PiggyBankMovement.objects.create(
                token=generate_token(PiggyBankMovement),
                piggy_bank=bail.contract.piggy_bank,
                amount=bail.amount,
                is_positive=True,
                movement_date=timezone.now(),
                bail=bail,
            )
            bail.contract.piggy_bank.amount += bail.amount
            bail.contract.piggy_bank.save()
        #check_unpaid_invoices(contracts)
        return Response({'message': 'Invoice returned successfully'}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='cancel')
    def cancel_bail(self, request):
        user = request.user
        bail_ids = request.data.get('bail_ids', [])
        
        query = Q(token__in=[str(x) for x in bail_ids])
        numeric_ids = [int(x) for x in bail_ids if str(x).isdigit()]
        if numeric_ids:
            query |= Q(id__in=numeric_ids)
        bails = Bail.objects.filter(query)
        
        cancel_token_config = ConfigProject.objects.filter(token='bail_status_cancelled_token').first()
        cancel_status = BailStatus.objects.filter(token=cancel_token_config.value).first() if cancel_token_config else BailStatus.objects.filter(token='-1').first()
        
        for bail in bails:
            prev_status = bail.status
            if cancel_status:
                bail.status = cancel_status
            bail.is_active = False
            bail.save()
            
            LogBailStatus.objects.create(
                object=bail,
                previous_status=prev_status,
                current_status=bail.status,
                user=user,
                timestamp=timezone.now(),
                observation="Bail cancelled"
            )
            
        return Response({'message': 'Bails cancelled successfully'}, status=status.HTTP_200_OK)

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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'bail')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'bail', 'contract')
        return Response(permissions, status=status.HTTP_200_OK)
        
    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()