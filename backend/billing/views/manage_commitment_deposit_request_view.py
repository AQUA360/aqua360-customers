from decimal import Decimal
import hashlib
import uuid
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.db.models import Q, Max, OuterRef, Exists, Count, Sum
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import CommitmentDeposit, CommitmentDepositStatus, Invoice, InvoiceStatus, Payment, PaymentCommitment, PaymentCommitmentStatus, PaymentStatus
from billing.serializers.commitment_deposit_serializer import CommitmentDepositListSerializer
from billing.serializers.invoice_serializer import InvoiceFullSerializer
from billing.utils.barcode_service import repeat_to_at_least_length
from contract.models import Contract, ContractRequest, PaymentType
from coredata.models import ConfigProject, Person
from logger.models import LogCommitmentDepositMovement

class ManageCommitmentDepositRequestViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = CommitmentDeposit.objects.all().order_by('-created_at')
    def post(self, request, *args, **kwargs):
        #payment_ids = request.data["payment_ids"]
        step = request.data["step"]
        found_request = request.data["found_request"] if "found_request" in request.data else False
        selected_contract = request.data["selected_contract"] if "selected_contract" in request.data else None
        selected_invoice = request.data["selected_invoice"] if "selected_invoice" in request.data else None
        selected_person = request.data["selected_person"] if "selected_person" in request.data else None
        
        payments = request.data["payments"] if "payments" in request.data else None
        holder = request.data["holder"] if "holder" in request.data else None
        contract = request.data["contract"] if "contract" in request.data else None
        invoices = request.data["invoices"] if "invoices" in request.data else None
        
        days_next_payment = request.data["days_next_payment"] if "days_next_payment" in request.data else None
        due_date_commitment = request.data["due_date_commitment"] if "due_date_commitment" in request.data else None
        start_date_commitment = request.data.get("start_date_commitment") or None
        
        request_instance = request.data["request"] if "request" in request.data else None
        
        print("Manage Commitment Deposit Generate View")
        print(step)
        print(selected_contract)
        print(selected_person)
        print(selected_invoice)
        print(payments)
        print(holder)
        
        tenant = None
        owner = None
        
        paid_invoice_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_paid_token').value)
        payoff_invoice_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_payoff_token').value)
        dropped_invoice_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_dropped_token').value)
        pending_invoice_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_pending_token').value)
        commitment_invoice_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_commitment_token').value)
        invoice_status_cancelled = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_cancelled_token').value)
        expired_invoice_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_expired_token').value)
        commitment_payment_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_commitment_token').value)
        paid_payment_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
        
        partially_paid_commitment_deposit_status = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_partially_paid_token').value)
        pending_commitment_deposit_status = CommitmentDepositStatus.objects.get(token=ConfigProject.objects.get(token='commitment_deposit_status_pending_token').value)
        pending_payment_commitment_status = PaymentCommitmentStatus.objects.get(token=ConfigProject.objects.get(token='payment_commitment_status_pending_token').value)
        defaul_commitment_deposit_status = CommitmentDepositStatus.objects.get(is_default=True)
        default_payment_commitment_status = PaymentCommitmentStatus.objects.get(is_default=True)
        
        if step == '1':
            deposits = None
            if found_request:
                print("invoices: ", invoices)
                invoices = Invoice.objects.filter(id__in=invoices).distinct()
            else:
                holder = None
                contract_instance = None
                deposits_found = []
                print("fetching")
                filters = Q()
                if selected_contract:
                    holder = {
                        'id': selected_contract.get('holder'),
                        'token': selected_contract.get('holder_token'),
                        'name': selected_contract.get('holder_full_name'),
                    }
                    contract = {
                        'id': selected_contract.get('id'),
                        'token': selected_contract.get('token'),
                    }
                    print("selected_contract: ", selected_contract)
                    if selected_contract.get('tenant'):
                        tenant = {
                            'id': selected_contract.get('tenant'),
                            'token': selected_contract.get('tenant_token'),
                            'name': selected_contract.get('tenant_full_name'),
                        }
                    if selected_contract.get('owner'):
                        owner = {
                            'id': selected_contract.get('owner'),
                            'token': selected_contract.get('owner_token'),
                            'name': selected_contract.get('owner_full_name'),
                        }
                    try:
                        contract_instance = Contract.objects.get(id=selected_contract.get('id'))
                        contract_request_id = ContractRequest.objects.get(token=contract_instance.token).id # contract_instance.contract_request.id
                        print("contract_request_id: ", contract_request_id)
                    except:
                        contract_request_id = None
                    filters &= ~Q(status__in=[paid_invoice_status, pending_invoice_status, commitment_invoice_status, invoice_status_cancelled, payoff_invoice_status, dropped_invoice_status])
                    filters &= ~Q(payments__remittances__id__isnull=False, payments__remittances__sent_at__isnull=True)
                    contract_filters = Q(contract__id=selected_contract.get('id'))
                    if contract_request_id:
                        contract_filters |= Q(contract_request__id=contract_request_id)
                    filters &= contract_filters
                    print("filters: ", filters)
                    deposits_found = CommitmentDeposit.objects.filter(contract__id=selected_contract.get('id'), status__in=[pending_commitment_deposit_status, partially_paid_commitment_deposit_status]).distinct()
                    
                    invoices = Invoice.objects.filter(filters).distinct()
                    print("invoices: ", invoices)
                    for invoice in invoices:
                        print("invoice: ", invoice.serie_final)
                
                
                """ if selected_person:
                    holder = {
                        'token': selected_person.get('token'),
                        'name': selected_person.get('full_name'),
                    }
                    print("selected_person")
                    print(selected_person)
                    print(selected_person.get('token'))
                    #either person or person id
                    filters &= Q(customer_token_final=selected_person.get('token')) """
                
                if selected_invoice:
                    invoices = Invoice.objects.filter(id=selected_invoice.get('id')).distinct()
                    deposits_found = CommitmentDeposit.objects.filter(contract__id=selected_invoice.get('contract'), status__in=[pending_commitment_deposit_status, partially_paid_commitment_deposit_status]).distinct()
                    contract_instance = None
                    if selected_invoice.get('contract'):
                        try:
                            contract_instance = Contract.objects.get(id=selected_invoice.get('contract'))
                        except Contract.DoesNotExist:
                            pass
                    elif selected_invoice.get('contract_request'):
                        try:
                            contract_instance = Contract.objects.get(contract_request__id=selected_invoice.get('contract_request'))
                        except Contract.DoesNotExist:
                            try:
                                contract_request = ContractRequest.objects.get(id=selected_invoice.get('contract_request'))
                                contract_instance = Contract.objects.get(token=contract_request.token)
                            except (ContractRequest.DoesNotExist, Contract.DoesNotExist):
                                pass
                    
                    
                    
                    if contract_instance:
                        contract = {
                            'id': contract_instance.id,
                            'token': contract_instance.token,
                        }
                        holder = {
                            'id': contract_instance.holder.id,
                            'token': contract_instance.holder.token,
                            'name': f'{contract_instance.holder.name} {contract_instance.holder.surname}',
                        }
                        if contract_instance.tenant:
                            tenant = {
                                'id': contract_instance.tenant.id,
                                'token': contract_instance.tenant.token,
                                'name': f'{contract_instance.tenant.name} {contract_instance.tenant.surname}',
                            }
                        if contract_instance.owner:
                            owner = {
                                'id': contract_instance.owner.id,
                                'token': contract_instance.owner.token,
                                'name': f'{contract_instance.owner.name} {contract_instance.owner.surname}',
                            }
                    else:
                        print("selected_invoice: ", selected_invoice)
                        contract = None
                        holder = {
                            'id': None,
                            'token': selected_invoice.get('customer_token_final'),
                            'name': selected_invoice.get('customer_final'),
                        }
                    
                
                if len(deposits_found) > 0:
                    deposits = CommitmentDepositListSerializer(deposits_found, many=True).data
                
            serialized_invoices = InvoiceFullSerializer(invoices, many=True).data
            print("invoices")
            print(invoices)
            print(len(invoices))
                
            return_data = {
                "invoices": serialized_invoices,
                "holder": holder,
                "tenant": tenant,
                "owner": owner,
                "contract": contract,
                "deposits": deposits
            }
            return Response(return_data, status=status.HTTP_200_OK)
        
        elif step == '4':
            if request_instance:
                print("\nrequest_instance: ", request_instance)
                deposit = CommitmentDeposit.objects.get(id=request_instance.get('id'))
                invoice_ids = [i.get('id') for i in invoices]
                print("invoice_ids: ", invoice_ids)
                logger_data = {
                    "object": deposit,
                    "previous_remaining": deposit.remaining,
                    "current_remaining": deposit.remaining + Decimal(sum(float(p.get('amount')) for p in payments)),
                    "user": request.user if request.user else None,
                }
                
                log = LogCommitmentDepositMovement.objects.create(**logger_data)
                
                log.new_invoices.set(invoice_ids)
                
                print("remaining: ", deposit.remaining)
                print("new remaining: ", float(deposit.remaining) + sum(float(p.get('amount')) for p in payments))
                deposit.remaining += Decimal(sum(float(p.get('amount')) for p in payments))
                deposit.due_date = due_date_commitment
                deposit.total += Decimal(sum(float(p.get('amount')) for p in payments))
                
                payment_instances = Payment.objects.filter(invoice__id__in=invoice_ids).distinct()
                for payment in payment_instances:
                    if payment.status.token != paid_payment_status.token:
                        payment.status = commitment_payment_status
                        payment.save()
                
                deposit.invoices.add(*invoice_ids)
                deposit.save()
                
                for payment in payments:
                    payment_data = {
                        "token": generate_commitment_id(),
                        "status": default_payment_commitment_status,
                        "commitment_deposit": deposit,
                        "currently_paid": 0.00,
                        "amount": float(payment.get('amount')),
                        "start_date": payment.get('start_date') or None,
                        "due_date": payment.get('due_date'),
                        "is_guide": True,
                    }
                    
                    payment_commitment = PaymentCommitment.objects.create(**payment_data)
                
                
                
                return Response({'ok': 'ok'}, status=status.HTTP_200_OK)
            else:
                
                #holder_instance = Person.objects.get(token=holder['token'])
                contract_instance = None
                if contract and 'id' in contract and contract['id']:
                    contract_instance = Contract.objects.get(id=contract['id'])
                
                commitment_deposit_data = {
                    "token": generate_commitment_id(),
                    "total": sum(float(p.get('amount')) for p in payments),
                    "remaining": sum(float(p.get('amount')) for p in payments),
                    "status": defaul_commitment_deposit_status,
                    "days_next_payment": days_next_payment,
                    "start_date": start_date_commitment,
                    "due_date": due_date_commitment,
                    "contract": contract_instance,
                    "customer_final": holder.get('name') if holder else invoices[0].get('customer_final'),
                    "customer_token_final": holder.get('token') if holder else invoices[0].get('customer_token_final'),
                    "address_final": invoices[0].get('address_final'),
                    "location_final": invoices[0].get('location_final'),
                    "persons_final": invoices[0].get('persons_final'),
                }
                
                
                commitment_deposit = CommitmentDeposit.objects.create(**commitment_deposit_data)
                #set invoice from commitment deposit with ids in invoices
                invoice_ids = [i.get('id') for i in invoices]
                payment_instances = Payment.objects.filter(invoice__id__in=invoice_ids).distinct()
                #using for instead of update() to trigger signal
                #payment_instances.update(status=commitment_payment_status)
                for payment in payment_instances:
                    if payment.status.token != paid_payment_status.token:
                        payment.status = commitment_payment_status
                        payment.save()
                commitment_deposit.invoices.set(invoice_ids)
                commitment_deposit.save()
                
                counter = 0
                for payment in payments:
                    payment_data = {
                        "token": commitment_deposit.token + repeat_to_at_least_length('0', 2 - len(str(counter))) + str(counter),
                        "status": default_payment_commitment_status,
                        "commitment_deposit": commitment_deposit,
                        "currently_paid": 0.00,
                        "amount": float(payment.get('amount')),
                        "start_date": payment.get('start_date') or None,
                        "due_date": payment.get('due_date'),
                        "is_guide": True,
                    }
                    counter += 1
                    
                    payment_commitment = PaymentCommitment.objects.create(**payment_data)
                
                return Response({'ok': 'ok'}, status=status.HTTP_200_OK)
            
        
        return Response({"error": "Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)

def generate_commitment_id():
    max_serie = CommitmentDeposit.objects.all().aggregate(max_serie=Max('token'))['max_serie']
    next_num = 1
    if max_serie:
        try:
            last_part = max_serie[-7:]
            current_num = int(last_part)
            next_num = current_num + 1
        except (ValueError, IndexError):
            pass
    return '03' + str(next_num).zfill(7)