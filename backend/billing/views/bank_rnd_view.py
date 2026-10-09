# views.py (or wherever your API view is defined)
import datetime
from decimal import Decimal
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import xml.etree.ElementTree as ET
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import BankRNDDocument, CommitmentDeposit, Invoice, InvoiceStatus, JoinedPayment, JoinedPaymentStatus, Payment, PaymentMovement, PaymentStatus
from billing.utils.invoice_service import generate_payment_id
from billing.utils.joined_payment_service import mark_payments_as_paid, register_joined_payment_log
from contract.models import Contract, PaymentType, PiggyBankMovement
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token


class BankRNDDocumentView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all().order_by('-created_at')

    @staticmethod
    def _build_register_data(
        line, amount, contract, status_name, status_color,
        is_paid, payment_id, joined_payment_id, is_joined,
        contract_request=None, invoice=None, commitment_deposit=None,
    ):
        return {
            'payment_date': line[30:36],
            'amount': amount,
            'identifier': line[48:54],
            'reference': line[76:90],
            'contract': contract,
            'status_name': status_name,
            'status_color': status_color,
            'is_paid': is_paid,
            'save_balance': False,
            'payment_id': payment_id,
            'joined_payment_id': joined_payment_id,
            'is_joined': is_joined,
            'contract_request': contract_request,
            'invoice': invoice,
            'commitment_deposit': commitment_deposit,
        }

    @staticmethod
    def _barcode_reference_from_line(line):
        if len(line) >= 90:
            return line[76:90].strip()
        return line[76:].strip()

    @staticmethod
    def _contract_token_from_barcode_reference(barcode_reference):
        ref = (barcode_reference or "").strip()
        if len(ref) < 7:
            return None
        return ref[:-2][-5:]

    @classmethod
    def _find_contract_by_token_code(cls, contract_token):
        if not contract_token:
            return None
        contract = Contract.objects.filter(token=contract_token).first()
        if contract:
            return contract
        stripped = contract_token.lstrip("0")
        if stripped:
            contract = Contract.objects.filter(token=stripped).first()
            if contract:
                return contract
        return Contract.objects.filter(token=contract_token.zfill(5)).first()

    @classmethod
    def _match_invoice_by_barcode_contract(cls, line, total, type_final, matchable_statuses):
        barcode_ref = cls._barcode_reference_from_line(line)
        contract_token = cls._contract_token_from_barcode_reference(barcode_ref)
        contract = cls._find_contract_by_token_code(contract_token)
        if not contract:
            return None, None, None

        invoice = (
            Invoice.objects.filter(
                contract=contract,
                status__in=matchable_statuses,
                type_final=type_final,
                is_active=True,
            )
            .filter(Q(left_to_pay=total) | Q(total_final=total))
            .order_by("-issue_date", "-id")
            .first()
        )
        if not invoice:
            return contract, None, None

        payment = invoice.payments.order_by("-created_at").first()
        return contract, invoice, payment

    def _apply_rnd_paid_state(
        self,
        *,
        line,
        payment,
        invoice,
        is_saving,
        payment_origin,
        payment_type,
        status_paid,
        status_cancelled,
        invoices_to_update,
        request,
    ):
        payment_previous_status = payment.status
        paid_on = datetime.datetime.strptime(line[30:36], "%d%m%y").date()
        payment.status = status_paid
        payment.paid_at = paid_on
        payment.payment_date = paid_on
        if is_saving and payment_previous_status != status_paid and payment_previous_status != status_cancelled:
            if invoice:
                invoice.payment_type_final = payment_type.name
                invoice.payment_type_token_final = payment_type.token
                invoices_to_update.append(invoice)
            payment.payment_type = payment_type.name
            payment.payment_type_token = payment_type.token
            payment.payment_origin_choice = payment_origin
            payment.save()
            if payment_origin:
                last_movement = (
                    PaymentMovement.objects.filter(
                        payment=payment,
                        is_positive=True,
                        payment_type__token=payment_type.token,
                    )
                    .order_by("-timestamp")
                    .first()
                )
                if last_movement:
                    last_movement.payment_origin = payment_origin
                    last_movement.save()

        contract = None
        contract_request = None
        if invoice and invoice.contract:
            contract = {
                "id": invoice.contract.id,
                "token": invoice.contract.token,
                "holder": invoice.contract.holder.token if invoice.contract.holder else None,
            }
        elif invoice and invoice.contract_request:
            contract_request = {
                "id": invoice.contract_request.id,
                "token": invoice.contract_request.token,
                "holder": invoice.contract_request.holder.token if invoice.contract_request.holder else None,
            }
        invoice_data = {"id": invoice.id, "token": invoice.token} if invoice else None
        return payment_previous_status, contract, contract_request, invoice_data

    def post(self, request, *args, **kwargs):
        payment_ids = request.data.get('payments')
        payment_origin = request.data.get('payment_origin')
        try:
            status_piggy_bank = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_piggy_token').value)
            balance_payment_type = PaymentType.objects.get(token="BALANCE")
            payments = Payment.objects.filter(id__in=payment_ids)
            
            payments_without_contract = []
            for payment in payments:
                contract = None
                if payment.contract:
                    contract = payment.contract
                elif payment.invoice:
                    if payment.invoice.contract:
                        contract = payment.invoice.contract
                    elif payment.invoice.contract_request:
                        contract = Contract.objects.get(contract_request=payment.invoice.contract_request)
                    elif payment.invoice.contract_termination:
                        contract = payment.invoice.contract_termination.contract
                elif payment.commiment_deposit:
                    contract = payment.commiment_deposit.contract
                if not contract:
                    payments_without_contract.append(payment.id)
                    continue
                
                piggy_bank = contract.piggy_bank
                piggy_bank.amount += payment.amount
                piggy_bank.save()
                
                # Update original payment status
                from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
                previous_status = payment.status
                disconnect_payment_signals()
                payment.status = status_piggy_bank
                payment.payment_origin_choice = payment_origin
                payment.save()
                reconnect_payment_signals()

                # Create PaymentMovement with origin 
                # NOT FOR OG PAYMENT
                """ PaymentMovement.objects.create(
                    user=request.user,
                    payment=payment,
                    movement_date=datetime.datetime.now().date(),
                    previous_status=previous_status,
                    current_status=status_piggy_bank,
                    is_positive=True,
                    payment_origin=payment_origin
                ) """

                PiggyBankMovement.objects.create(
                    token=generate_token(PiggyBankMovement),
                    piggy_bank=piggy_bank,
                    amount=payment.amount,
                    is_positive=True,
                    movement_date=datetime.datetime.now().date(),
                    payment=payment,
                )
                try:
                    new_payment = Payment.objects.create(
                        token=generate_payment_id(payment.token[:2]),
                        name=contract.token,
                        status=status_piggy_bank,
                        contract=contract,
                        amount=payment.amount,
                        due_date=datetime.datetime.now().date() + datetime.timedelta(days=30),
                        payment_date=datetime.datetime.now().date(),
                        payment_type=balance_payment_type.name,
                        payment_type_token=balance_payment_type.token,
                        address_final=payment.address_final,
                        location_final=payment.location_final,
                        customer_final=payment.customer_final,
                        customer_token_final=payment.customer_token_final,
                        payer_final=payment.payer_final,
                        payer_token_final=payment.payer_token_final,
                    )
                    PaymentMovement.objects.create(
                        user=request.user,
                        payment=new_payment,
                        movement_date=datetime.datetime.now().date(),
                        current_status=status_piggy_bank,
                        is_positive=True,
                        payment_origin=payment_origin
                    )
                except Exception as e:
                    print("COULD NOT CREATE PAYMENT: ", e)
                    
                
            return Response({'message': 'Payments updated'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, *args, **kwargs):
        from billing.utils.payment_service import reconnect_payment_signals
        reconnect_payment_signals()
        
        file = request.data.get("file")
        is_saving = request.data.get("is_saving", False)
        payment_origin = request.data.get("payment_origin")
        user = request.user
        if not isinstance(is_saving, bool):
            is_saving = is_saving.lower() == 'true'
        print("is_saving: ", is_saving)
        if not file:
            return Response(
                {"error": "No file was uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            file_name = file.name
            file_content = file.read()
            if isinstance(file_content, bytes):
                file_content = file_content.decode("utf-8")
            
            lines = file_content.splitlines()
            header = lines[0]
            header_transmitter = lines[1]
            
            doc_exists = False
            try:
                bank_rnd_document = BankRNDDocument.objects.get(file_name=file_name, first_line=header)
                doc_exists = True
            except:
                bank_rnd_document = BankRNDDocument.objects.create(
                    token=generate_token(BankRNDDocument),
                    file_name=file_name,
                    first_line=header,
                    user=user,
                )
            
            body = lines[2:-2]
            #total_register_suffix is the last line of the file
            total_register_suffix = lines[-2]
            final_register_suffix = lines[-1]
            
            #payment_date -> ZONA E E3 (POS 31 6 CHARS)
            #total -> ZONA F (POS 37 12 CHARS)
            #identifier -> ZONA G (POS 49 6 CHARS)
            #reference -> ZONA J J2 (POS 77 13 CHARS)
            type_final = ConfigProject.objects.get(token='invoice_type_invoice_token').value
            status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
            status_pending = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_pending_token').value)
            status_expired = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_expired_token').value)
            status_cancelled = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_cancelled_token').value)
            status_confirmed = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)
            # Les factures pagades per taquilla/correus solen estar ja en estat "Enviada" o "Vençuda"
            # (no només "Confirmada"), ja que el client les paga temps després d'haver-les rebut.
            barcode_contract_matchable_statuses = list(
                InvoiceStatus.objects.filter(token__in=[status_confirmed.token, '3', '-1'])
            )
            joined_payment_status_paid = JoinedPaymentStatus.objects.get(token=ConfigProject.objects.get(token='joined_payment_status_paid_token').value)
            payment_type = PaymentType.objects.get(token="BANK_PAYMENT")
            #status_com_payment_pending = PaymentCommitmentStatus
            invoices_to_update = []
            payment_previous_status = None
            data = []
            for line in body:
                amount = line[36:46]
                decimals = line[46:48]
                
                payment_date = line[48:54]
                payment = None
                total = Decimal(f"{amount}.{decimals}")
                invoice = None
                invoice_data = None
                commitment_deposit_data = None
                contract = None
                contract_request = None
                
                try:
                    """ print("\n\nLINESTRAT")
                    print(line[76:78]) """
                    if line[76:78] == '01' or line[76:78] == '02':
                        invoice = Invoice.objects.get(token=line[76:87], type_final=type_final)
                        
                        payment = invoice.payments.order_by('-created_at').first()
                        
                        payment_previous_status = payment.status
                        """ if is_saving and payment_origin:
                            if payment_previous_status == status_paid:
                                if not PaymentMovement.objects.filter(payment=payment, payment_origin__isnull=False).exists():
                                    last_movement = PaymentMovement.objects.filter(payment=payment).order_by('-timestamp').first()
                                    if last_movement:
                                        last_movement.payment_origin = payment_origin
                                        last_movement.save()
                                    else:
                                        PaymentMovement.objects.create(
                                            user=request.user,
                                            payment=payment,
                                            movement_date=payment.payment_date or datetime.datetime.now().date(),
                                            current_status=payment.status,
                                            is_positive=True,
                                            payment_origin=payment_origin
                                        ) """
                        payment.status = status_paid
                        payment.paid_at = datetime.datetime.strptime(line[30:36], "%d%m%y").date()
                        payment.payment_date = datetime.datetime.strptime(line[30:36], "%d%m%y").date()
                        if is_saving and payment_previous_status != status_paid and payment_previous_status != status_cancelled:
                            invoice.payment_type_final = payment_type.name
                            invoice.payment_type_token_final = payment_type.token
                            invoices_to_update.append(invoice)
                            payment_previous_status = payment.status
                            payment.payment_type = payment_type.name
                            payment.payment_type_token = payment_type.token
                            payment.payment_origin_choice = payment_origin
                            payment.save()
                            if payment_origin:
                                last_movement = PaymentMovement.objects.filter(payment=payment, is_positive=True, payment_type__token=payment_type.token).order_by('-timestamp').first()
                                if last_movement:
                                    last_movement.payment_origin = payment_origin
                                    last_movement.save()
                        if invoice.contract:
                            contract = {
                                'id': invoice.contract.id,
                                'token': invoice.contract.token,
                                'holder': invoice.contract.holder.token,
                            }
                        elif invoice.contract_request:
                            contract_request = {
                                'id': invoice.contract_request.id,
                                'token': invoice.contract_request.token,
                                'holder': invoice.contract_request.holder.token,
                            }
                        invoice_data = {
                            'id': invoice.id,
                            'token': invoice.token,
                        }
                    elif line[76:78] == '03':
                        print("line: ", line[76:87])
                        payment = Payment.objects.filter(token=line[76:87], status__in=[status_pending, status_expired, status_paid], commitment_deposit__isnull=False).first()
                        if not payment:
                            payment = Payment.objects.filter(
                                commitment_deposit__token=line[76:87], status__in=[status_pending, status_expired, status_paid], amount=total
                                ).first()
                        if not payment:
                            payment = Payment.objects.filter(
                                token__startswith=line[76:87], status__in=[status_pending, status_expired, status_paid], amount=total
                                ).first()
                        commitment_deposit = payment.commitment_deposit
                        
                        payment_previous_status = payment.status
                        """ if is_saving and payment_origin:
                            if payment_previous_status == status_paid:
                                if not PaymentMovement.objects.filter(payment=payment, payment_origin__isnull=False).exists():
                                    last_movement = PaymentMovement.objects.filter(payment=payment).order_by('-timestamp').first()
                                    if last_movement:
                                        last_movement.payment_origin = payment_origin
                                        last_movement.save()
                                    else:
                                        PaymentMovement.objects.create(
                                            user=request.user,
                                            payment=payment,
                                            movement_date=payment.payment_date or datetime.datetime.now().date(),
                                            current_status=payment.status,
                                            is_positive=True,
                                            payment_origin=payment_origin
                                        ) """
                        payment.status = status_paid
                        payment.paid_at = datetime.datetime.strptime(line[30:36], "%d%m%y").date()
                        payment.payment_date = datetime.datetime.strptime(line[30:36], "%d%m%y").date()
                        if is_saving and payment_previous_status != status_paid and payment_previous_status != status_cancelled:
                            payment_previous_status = payment.status
                            payment.payment_type = payment_type.name
                            payment.payment_type_token = payment_type.token
                            payment.payment_origin_choice = payment_origin
                            payment.save()
                            if payment_origin:
                                last_movement = PaymentMovement.objects.filter(payment=payment, is_positive=True, payment_type__token=payment_type.token).order_by('-timestamp').first()
                                if last_movement:
                                    last_movement.payment_origin = payment_origin
                                    last_movement.save()
                        commitment_deposit_data = {
                            'id': commitment_deposit.id,
                            'token': commitment_deposit.token,
                        }
                        contract = {
                            'id': commitment_deposit.contract.id,
                            'token': commitment_deposit.contract.token,
                            'holder': commitment_deposit.contract.holder.token,
                        }
                    elif line[76:78] == '05':
                        try:
                            joined_payment = JoinedPayment.objects.get(token=line[76:87])
                            payments = joined_payment.payments.all()
                            if joined_payment.contract:
                                contract = {
                                    'id': joined_payment.contract.id,
                                    'token': joined_payment.contract.token,
                                    'holder': joined_payment.contract.holder.token,
                                }
                            data.append(self._build_register_data(
                                line=line, amount=total, contract=contract,
                                status_name=joined_payment.status.name if not is_saving else joined_payment_status_paid.name,
                                status_color=joined_payment.status.color if not is_saving else joined_payment_status_paid.color,
                                is_paid=False, payment_id=None,
                                joined_payment_id=joined_payment.id,
                                is_joined=True,
                            ))
                            for payment in payments:
                                invoice = payment.invoice
                                commitment_deposit = payment.commitment_deposit
                                invoice_data = None
                                commitment_deposit_data = None
                                if invoice:
                                    invoice_data = {
                                        'id': invoice.id,
                                        'token': invoice.token,
                                    }
                                if commitment_deposit:
                                    commitment_deposit_data = {
                                        'id': commitment_deposit.id,
                                        'token': commitment_deposit.token,
                                    }
                                
                                try:
                                    already_in_balance = PiggyBankMovement.objects.filter(payment=payment).exists()
                                except:
                                    already_in_balance = False
                                
                                if already_in_balance or is_saving:
                                    is_paid = False
                                else:
                                    is_paid = payment.status == status_paid if payment else None
                                
                                register_data = self._build_register_data(
                                    line=line, amount=payment.amount, contract=contract,
                                    status_name=payment.status.name if not is_saving else status_paid.name,
                                    status_color=payment.status.color if not is_saving else status_paid.color,
                                    is_paid=is_paid,
                                    payment_id=payment.id if payment else None,
                                    joined_payment_id=joined_payment.id,
                                    is_joined=False,
                                    invoice=invoice_data,
                                    commitment_deposit=commitment_deposit_data,
                                )
                                data.append(register_data)
                            
                            if is_saving and joined_payment.status != joined_payment_status_paid:
                                register_joined_payment_log(joined_payment, joined_payment.status, joined_payment_status_paid, None, user)
                                mark_payments_as_paid(joined_payment, user, payment_origin)
                                joined_payment.status = joined_payment_status_paid
                                joined_payment.save()
                            continue    
                        except Exception as e:
                            print("error 05: ", e)
                            continue
                    else:
                        try:
                            invoice = Invoice.objects.get(token=line[76:87])
                        except Exception:
                            invoice = None
                        if not invoice:
                            try:
                                invoice = Invoice.objects.get(token=line[76:85])
                            except Exception:
                                invoice = None
                        if invoice:
                            payment = invoice.payments.order_by('-created_at').first()
                            if payment:
                                payment_previous_status, contract, contract_request, invoice_data = self._apply_rnd_paid_state(
                                    line=line,
                                    payment=payment,
                                    invoice=invoice,
                                    is_saving=is_saving,
                                    payment_origin=payment_origin,
                                    payment_type=payment_type,
                                    status_paid=status_paid,
                                    status_cancelled=status_cancelled,
                                    invoices_to_update=invoices_to_update,
                                    request=request,
                                )
                    Invoice.objects.bulk_update(invoices_to_update, ['payment_type_final', 'payment_type_token_final'])
                except Exception as e:
                    print("error: ", e)
                    print("problem finding invoice and updating payment")

                #TODO: Borrar d'aquí uns mesos quan ja no hi hagin documents de pagaments històrics per carregar
                if payment is None:
                    _, invoice, payment = self._match_invoice_by_barcode_contract(
                        line, total, type_final, barcode_contract_matchable_statuses
                    )
                    if payment and invoice:
                        payment_previous_status, contract, contract_request, invoice_data = self._apply_rnd_paid_state(
                            line=line,
                            payment=payment,
                            invoice=invoice,
                            is_saving=is_saving,
                            payment_origin=payment_origin,
                            payment_type=payment_type,
                            status_paid=status_paid,
                            status_cancelled=status_cancelled,
                            invoices_to_update=invoices_to_update,
                            request=request,
                        )
                        Invoice.objects.bulk_update(invoices_to_update, ['payment_type_final', 'payment_type_token_final'])
                    
                try:
                    already_in_balance = PiggyBankMovement.objects.filter(payment=payment).exists()
                except:
                    already_in_balance = False
                
                if already_in_balance:
                    is_paid = False
                else:
                    is_paid = payment_previous_status == status_paid if payment and payment_previous_status else None
                register_data = self._build_register_data(
                    line=line, amount=total, contract=contract,
                    status_name=payment_previous_status.name if payment and payment_previous_status else None,
                    status_color=payment_previous_status.color if payment and payment_previous_status else None,
                    is_paid=is_paid,
                    payment_id=payment.id if payment else None,
                    joined_payment_id=None,
                    is_joined=False,
                    contract_request=contract_request,
                    invoice=invoice_data,
                    commitment_deposit=commitment_deposit_data,
                )
                
                data.append(register_data)
            
            
            
            print("register_data")
            # print(data)
            
            return Response({'data': data, 'document_exists': doc_exists }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Error processing file: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    