from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q, OuterRef, Exists, Sum
from billing.models import Invoice, Payment, PaymentStatus
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from billing.serializers.payment_serializer import PaymentSerializer
from contract.models import Contract, ContractTerminationRequest
from contract.serializers.contract_serializer import ContractListSerializer
from coredata.models import ConfigProject, PersonDeliquency
from service.models import SupplyCut
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
class ManageDeliquencyViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all().order_by('-created_at')
    def post(self, request, *args, **kwargs):
        date_start = request.data.get('date_start', None)
        date_end = request.data.get('date_end', None)
        sel_type = request.data.get('type', None)
        is_fetching = request.data.get('fetching', None)
        contract_ids = request.data.get('contracts', None)
        
        invoice_ids = request.data.get('invoices', None)
        is_saving = request.data.get('saving', None)
        
        print("values")
        print("date_start", date_start)
        print("date_end", date_end)
        print("sel_type", sel_type)
        print("is_fetching", is_fetching)
        print("contract_ids", contract_ids)
        
        payment_status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
        payment_status_endowment = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_endowment_token').value)
        payment_status_irrecoverable = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_irrecoverable_token').value)
        payment_status_pending = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
        payment_status_sent = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_sent_token').value)
        payment_status_returned = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
        payment_status_commitment = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_commitment_token').value)
        payment_status_expired = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
        if is_saving:
            print("is saving")
            if invoice_ids:
                print("with invoice ids")
                invoices = Invoice.objects.filter(id__in=invoice_ids)
                print("invoices", invoices)
                payments = Payment.objects.filter(invoice__in=invoices).exclude(status=payment_status_paid)
                for payment in payments:
                    payment.status = payment_status_endowment
                    payment.save()
                
                contracts = Contract.objects.filter(id__in=contract_ids)
                for contract in contracts:
                    contract_holder = contract.holder
                    last_invoice = invoices.filter(contract=contract).order_by('-created_at').first()
                    invoices_paid = invoices.filter(contract=contract).aggregate(total=Sum('left_to_pay'))['total']
                    invoices_total = invoices.filter(contract=contract).aggregate(total=Sum('total_final'))['total']
                    invoices_total -= invoices_paid
                    if invoices_total:
                        if contract_holder.deliquency:
                            contract_holder.deliquency.debt_amount += invoices_total
                            contract_holder.deliquency.last_debt_data = last_invoice.due_date #either this or today?
                            contract_holder.deliquency.save()
                        else:
                            contract_holder.deliquency = PersonDeliquency.objects.create(
                                debt_amount=invoices_total,
                                last_debt_data=last_invoice.due_date,
                                is_debtor=True,
                            )
                            contract_holder.save()
                return Response({"OK": "Management finished."}, status=status.HTTP_200_OK)
            else:
                raise Exception("No invoices provided")
        
        
        if is_fetching:
            print("saving")
            expired_token = ConfigProject.objects.get(token='invoice_status_expired_token').value
            invoices = Invoice.objects.filter(contract__id__in=contract_ids, status__token=expired_token)
            invoice_serializer = InvoiceMinimalSerializer(invoices, many=True)
            invoice_serializer.data.sort(key=lambda x: x['customer_token_final'])
            contracts = Contract.objects.filter(id__in=contract_ids)
            contract_serializer = ContractListSerializer(contracts, many=True)
            
            
            return Response({'invoices': invoice_serializer.data, 'contracts': contract_serializer.data}, status=status.HTTP_202_ACCEPTED)
        else:
            if date_start or date_end:
                print("fetching")
                filters = Q()
                contracts = Contract.objects.none()
                print("status irrecoverable", payment_status_irrecoverable)
                print("status paid", payment_status_paid)
                print("status endowment", payment_status_endowment)
                
                #excluded_statuses = [payment_status_irrecoverable, payment_status_paid, payment_status_endowment]
                #filters &= ~Q(payments__status__in=[payment_status_irrecoverable, payment_status_paid, payment_status_endowment])
                filters &= Q(payments__status__in=[payment_status_expired])
                
                if sel_type == 'PAYDATE' or sel_type == 'DUEDATE':
                    if sel_type == 'PAYDATE':
                        if date_start:
                            filters &= Q(payments__payment_date__gte=date_start)
                        if date_end:
                            filters &= Q(payments__payment_date__lte=date_end)
                    elif sel_type == 'DUEDATE':
                        if date_start:
                            filters &= Q(due_date__gte=date_start)
                        if date_end:
                            filters &= Q(due_date__lte=date_end)
                    invoices = Invoice.objects.filter(filters).distinct()
                    #get distinct contract from invoices
                    contract_ids = invoices.values_list('contract', flat=True)
                    print("contract_ids form invoices", contract_ids)
                    contracts = Contract.objects.filter(id__in=contract_ids)
                    
                if sel_type == 'TERMINATIONDATE':
                    if date_start:
                        filters &= Q(approved_at__gte=date_start)
                    if date_end:
                        filters &= Q(approved_at__lte=date_end)
                    terminations = ContractTerminationRequest.objects.filter(filters).distinct()
                    #get distinct contract from terminations
                    contract_ids = terminations.values_list('contract', flat=True)
                    contracts = Contract.objects.filter(id__in=contract_ids)
                    print("contract_ids from terminations", contract_ids)
                    
                if sel_type == 'SPCUT':
                    supply_cut_active = ConfigProject.objects.get(token="supply_cut_status_active_token").value
                    # «Indefinit» es defineix pel motiu (no temporal) i sense
                    # quarantena, no per la data de fi nul·la.
                    filters &= Q(
                        status__token=supply_cut_active,
                        requires_review=False,
                        cause__is_temporary=False,
                    )
                    if date_start:
                        filters &= Q(date_start__gte=date_start)
                    if date_end:
                        filters &= Q(date_start__lte=date_end)
                    supply_cut_subquery = SupplyCut.objects.filter(supply_point=OuterRef('supply_point_default')).filter(filters).values('id')
                    contracts = Contract.objects.filter(Exists(supply_cut_subquery)).distinct()
                    contract_ids = contracts.values_list('id', flat=True)
                    print("contracts from supply cuts", contracts)
                print("obtained contracts", contracts)
                
                contract_data = [{"id": contract.id, "token": contract.token, "holder": f"{contract.holder.name} {contract.holder.surname}", "holder_token": contract.holder.token} for contract in contracts]
            else:
                return Response(status=status.HTTP_202_ACCEPTED)
            
            return Response({'contract_data': contract_data}, status=status.HTTP_202_ACCEPTED)

    