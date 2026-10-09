from django.conf import settings
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from datetime import datetime
import json

from auth.permissions import PermissionManager
from billing.models import CommitmentDepositStatus, Invoice, InvoiceStatus, Payment, PaymentCommitment, PaymentCommitmentStatus, PaymentMovement, PaymentRemittanceReturn, PaymentStatus, RejectMotive
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from billing.serializers.payment_serializer import PaymentListSerializer, PaymentSerializer, PaymentSaveSerializer
from billing.filter.payment_filter import PaymentFilter

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from billing.utils.invoice_service import invoice_return_charge
from billing.utils.payment_service import disconnect_payment_signals, generate_payment_movement, get_sii_invoices, log_invoice_status, log_payment_status, reconnect_payment_signals
from coredata.utils.name_utils import generate_token
from documentmanager.utils.main_utils import upload_document
from claimrequest.models import ClaimRequest, ClaimRequestPayment, ClaimRequestStatus, ClaimRequestStep, ClaimRequestTemplate
from contract.models import Contract, PaymentType, PiggyBankMovement
from coredata.models import ConfigProject, PersonPiggyBankMovement
from logger.models import LogCommitmentDepositMovement

class PaymentOrderingFilter(OrderingFilter):
    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if ordering:
            new_ordering = []
            has_status_ordering = False
            for field in ordering:
                if field == 'status':
                    has_status_ordering = True
                    new_ordering.extend(['is_not_pending', 'status__position', 'status_id'])
                elif field == '-status':
                    has_status_ordering = True
                    new_ordering.extend(['-is_not_pending', '-status__position', '-status_id'])
                else:
                    new_ordering.append(field)

            if has_status_ordering:
                from django.db.models import Case, When, Value, IntegerField
                try:
                    pending_token = ConfigProject.objects.get(token='payment_status_pending_token').value
                except Exception:
                    pending_token = '1'
                
                queryset = queryset.annotate(
                    is_not_pending=Case(
                        When(status__token=pending_token, then=Value(0)),
                        default=Value(1),
                        output_field=IntegerField()
                    )
                )
            return queryset.order_by(*new_ordering)
        return queryset


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.filter(is_active=True)
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    filterset_class = PaymentFilter
    filter_backends = [DjangoFilterBackend, PaymentOrderingFilter]

    ordering = ['-is_excluded', 'status', '-created_at', 'due_date']

    
    ordering_fields = [
            'id', 'token', 'amount', 'due_date', 'payment_date',
            'reject__name', 'reject__token',
            'status__name', 'status__token', 'status',
            'created_at', 'updated_at',
            'payment_type', 'payment_type_token', 'payment_origin'
        ]

    search_fields = '__all__'

    def get_queryset(self):
        movements = PaymentMovement.objects.filter(
            payment=OuterRef('pk'),
            payment_origin__isnull=False
        ).order_by('-timestamp')
        return super().get_queryset().annotate(
            payment_origin=Subquery(movements.values('payment_origin')[:1])
        )

    def get_serializer_class(self):
        if self.request.method in ['GET']:
            if self.action == 'list':
                return PaymentListSerializer
            return PaymentSerializer
        return PaymentSaveSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = PaymentSerializer(instance)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = PaymentSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    def _parse_multipart_json_field(self, value, default=None):
        if default is None:
            default = []
        if value is None or value == '':
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default
        return value

    def _parse_date_value(self, raw):
        if not raw:
            return None
        try:
            if isinstance(raw, str):
                return datetime.strptime(raw.split('T')[0], "%Y-%m-%d").date()
            if isinstance(raw, datetime):
                return raw.date()
            if hasattr(raw, 'year'):
                return raw
        except (ValueError, TypeError) as exc:
            print("Error parsing date:", exc)
        return None

    def _get_rejection_item(self, payments_to_return_data, payment_id):
        return next(
            (
                item for item in payments_to_return_data
                if item.get('id') == payment_id or item.get('payment_id') == payment_id
            ),
            {},
        )

    def _resolve_rejection_date(self, rejection, return_date, payment):
        return (
            self._parse_date_value(rejection.get('rjt_dt'))
            or return_date
            or payment.payment_date
            or payment.paid_at
            or timezone.now().date()
        )

    @action(detail=False, methods=['post'], url_path='manage-rejection-payments')
    def manage_rejection_payments(self, request):
        data = request.data
        payments_to_return_data = self._parse_multipart_json_field(data.get("payments_to_return"), [])
        return_payments = self._parse_multipart_json_field(data.get("return_payments"), [])
        claim_payments = self._parse_multipart_json_field(data.get("claim_payments"), [])
        main_return_reason = data.get("main_return_reason", None)
        invoice_reject = data.get("invoice_return_id", None)
        return_date = self._parse_date_value(data.get("return_date"))
        og_msg_id = data.get("og_msg_id", None)
        if isinstance(og_msg_id, str):
            og_msg_id = og_msg_id.strip()
            if og_msg_id.lower() in ('', 'undefined', 'null', 'none'):
                og_msg_id = None
        file = request.FILES.getlist('file')
        
        if not return_date and payments_to_return_data:
            return_date = self._parse_date_value(payments_to_return_data[0].get('rjt_dt'))
        
        reject = None
        
        all_rejections = RejectMotive.objects.all()
        if main_return_reason:
            try:
                reject = all_rejections.get(id=main_return_reason)
            except Exception as e:
                print(e)
        payment_paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
        invoice_paid_token = ConfigProject.objects.get(token='invoice_status_paid_token').value
        payment_returned_token = ConfigProject.objects.get(token='payment_status_returned_token').value
        payment_returned_status = PaymentStatus.objects.get(token=payment_returned_token)
        payment_cancelled_token = ConfigProject.objects.get(token='payment_status_cancelled_token').value
        invoice_confirmed_token = ConfigProject.objects.get(token='invoice_status_confirmed_token').value
        invoice_status_expired_token = ConfigProject.objects.get(token='invoice_status_expired_token').value
        commitment_deposit_paid_token = ConfigProject.objects.get(token='commitment_deposit_status_paid_token').value
        commitment_deposit_partially_paid_token = ConfigProject.objects.get(token='commitment_deposit_status_partially_paid_token').value
        commitment_deposit_partially_paid_status = CommitmentDepositStatus.objects.get(token=commitment_deposit_partially_paid_token)
        payment_commitment_paid_token = ConfigProject.objects.get(token='payment_commitment_status_paid_token').value
        payment_commitment_pending_token = ConfigProject.objects.get(token='payment_commitment_status_pending_token').value
        payment_commitment_paid_status = PaymentCommitmentStatus.objects.get(token=payment_commitment_paid_token)
        payment_commitment_pending_status = PaymentCommitmentStatus.objects.get(token=payment_commitment_pending_token)
        invoice_confirmed_status = InvoiceStatus.objects.get(token=invoice_confirmed_token)
        invoice_expired_status = InvoiceStatus.objects.get(token=invoice_status_expired_token)
        
        payments_to_return_ids = [
            pid
            for p in payments_to_return_data
            for pid in [p.get('id'), p.get('payment_id')]
            if pid is not None
        ]
        payments_to_return = Payment.objects.filter(id__in=payments_to_return_ids)
        invoices_to_update_rejection = []
        returned_payment_ids = set()
        
        try:
            remittance_return = None
            # if og_msg_id:
            #     remittance_return = PaymentRemittanceReturn.objects.filter(token=og_msg_id).first()
            if not remittance_return:
                remittance_return = PaymentRemittanceReturn.objects.create(
                    token=og_msg_id if og_msg_id else generate_token(PaymentRemittanceReturn),
                    return_date=return_date,
                    returned_by=request.user,
                )
        except Exception as e:
            print(e)
            remittance_return = None
        
        document = None
        
        if file and remittance_return:
            try:
                service = settings.DOCUMENT_MANAGER_SERVICES.get("billing")
                document = upload_document(file[0], 'REBUTS', 'RETORNS', remittance_return.id, remittance_return.token, '', service, file[0].name.replace(' ', '_').replace('/', '_'), remittance_return.created_at)
            except Exception as e:
                print(e)
        
        if remittance_return:
            remittance_return.payments.set(payments_to_return)
            remittance_return.document = document
            remittance_return.save()
        
        for payment in payments_to_return:
            
            
            rejection = self._get_rejection_item(payments_to_return_data, payment.id)
            # rjt_date mai és None (cau a payment_date / paid_at / avui): és la data contra la qual
            # es miren els moviments, per no tenir en compte moviments posteriors al retorn
            rjt_date = self._resolve_rejection_date(rejection, return_date, payment)
            movements_until_return = payment.movements.filter(movement_date__lte=rjt_date)
            last_movement = movements_until_return.order_by('-movement_date', '-timestamp').first()
            # El cobrament que es retorna és l'últim moviment de domiciliació cobrat; el payment_type
            # actual del pagament no serveix, perquè canvia si després es cobra per una altra via
            direct_debit_movement = movements_until_return.filter(
                payment_type__token='DIRECT_DEBIT',
                current_status__token=payment_paid_token,
            ).order_by('-movement_date', '-timestamp').first()
            if last_movement:
                is_direct_debit_return = direct_debit_movement is not None
            else:
                # Pagaments històrics sense moviments: només es pot mirar el tipus del pagament
                is_direct_debit_return = payment.payment_type_token == 'DIRECT_DEBIT'

            if is_direct_debit_return:
                rejection_motive = None

                if payment.reject_date and rjt_date and payment.reject_date > rjt_date:
                    continue
                
                try:
                    if rejection.get('motive_id'):
                        rejection_motive = all_rejections.get(id=rejection.get('motive_id'))
                        payment.reject = rejection_motive
                        if rejection.get('rjt_dt'):
                            payment.reject_date = rejection['rjt_dt'].split("T")[0] if isinstance(rejection['rjt_dt'], str) else rejection['rjt_dt']
                        elif rjt_date:
                            payment.reject_date = rjt_date
                        if payment.invoice:
                            payment.invoice.reject = payment.reject
                            invoices_to_update_rejection.append(payment.invoice)
                    else:
                        payment.reject = None
                except Exception as e:
                    print(e)
                    payment.reject = None
                # skip_return és per payment: si és True només s'actualitza el motiu (reject); no l'estat
                skip_return = rejection.get('skip_return', False)

                # Si aquest cobrament ja consta retornat amb el mateix motiu (p. ex. el fitxer es
                # torna a carregar), no se'n genera un segon retorn: només s'actualitza el motiu
                return_motive = rejection_motive if rejection_motive else reject
                previous_returns = payment.movements.filter(current_status=payment_returned_status)
                if direct_debit_movement:
                    previous_returns = previous_returns.filter(movement_date__gte=direct_debit_movement.movement_date)
                if return_motive:
                    previous_returns = previous_returns.filter(reject_motive=return_motive)
                else:
                    previous_returns = previous_returns.filter(reject_motive__isnull=True)
                if previous_returns.exists():
                    skip_return = True

                if not skip_return and ((payment.status.token == payment_paid_token and ((payment.invoice and payment.invoice.status and payment.invoice.status.token == invoice_paid_token) or payment.commitment_deposit)) or (payment.status.token == payment_cancelled_token)):
                    disconnect_payment_signals()
                    today = timezone.now().date()
                    if not last_movement or last_movement.current_status.token == payment_paid_token:
                        movement_date = rjt_date
                        log_payment_status(payment, payment_returned_status, request.user, movement_date)
                        generate_payment_movement(
                            payment, payment_returned_status,
                            movement_date, 'DIRECT_DEBIT',
                            direct_debit_movement.payment_bank if direct_debit_movement and direct_debit_movement.payment_bank else payment.payment_bank, request.user,
                            return_motive,
                            payment.remittances.filter(sent_at__isnull=False).order_by('-sent_at').first())
                        if payment.invoice:
                            log_invoice_status(payment.invoice, invoice_confirmed_status, request.user)
                        payment.status = payment_returned_status
                        if rejection.get('rjt_dt'):
                            payment.reject_date = rejection['rjt_dt'].split("T")[0] if isinstance(rejection['rjt_dt'], str) else rejection['rjt_dt']
                        payment.save()
                        returned_payment_ids.add(payment.id)
                        if payment.invoice:
                            payment.invoice.status = invoice_confirmed_status if payment.invoice.due_date > today else invoice_expired_status
                            payment.invoice.save()
                        if payment.commitment_deposit:
                            LogCommitmentDepositMovement.objects.create(
                                object=payment.commitment_deposit,
                                previous_remaining=payment.commitment_deposit.remaining,
                                current_remaining=payment.commitment_deposit.remaining + payment.amount,
                            )
                            if payment.commitment_deposit.status.token == commitment_deposit_paid_token:
                                payment.commitment_deposit.status = commitment_deposit_partially_paid_status
                            payment.commitment_deposit.remaining = float(payment.commitment_deposit.remaining) + float(payment.amount)
                            payment.commitment_deposit.remaining_to_share = float(payment.commitment_deposit.remaining_to_share) - float(payment.amount)
                            if payment.commitment_deposit.remaining_to_share < 0:
                                payment.commitment_deposit.remaining_to_share = 0
                            if payment.payment_type_token:
                                payment_type_obj = PaymentType.objects.filter(token=payment.payment_type_token).first()
                            try:
                                payment_to_return = PaymentCommitment.objects.filter(
                                commitment_deposit=payment.commitment_deposit,
                                is_guide=True,
                                amount=payment.amount,
                                status=payment_commitment_paid_status
                                ).order_by('due_date').first()
                                if payment_to_return:
                                    payment_to_return.status = payment_commitment_pending_status
                                    payment_to_return.currently_paid = 0
                                    payment_to_return.save()
                                else:
                                    PaymentCommitment.objects.create(
                                        token=f"{payment.commitment_deposit.token}{PaymentCommitment.objects.filter(commitment_deposit=payment.commitment_deposit).count() + 1}",
                                        commitment_deposit=payment.commitment_deposit,
                                        is_guide=True,
                                        amount=payment.amount,
                                        status=payment_commitment_pending_status,
                                        due_date=payment.due_date,
                                    )
                            except PaymentCommitment.DoesNotExist as e:
                                PaymentCommitment.objects.create(
                                token=f"{payment.commitment_deposit.token}{PaymentCommitment.objects.filter(commitment_deposit=payment.commitment_deposit).count() + 1}",
                                commitment_deposit=payment.commitment_deposit,
                                is_guide=True,
                                amount=payment.amount,
                                status=payment_commitment_pending_status,
                                due_date=payment.due_date,
                                )
                            except Exception as e:
                                return Response(
                                    {"detail": "Error returning payment: " + str(e)},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                                )
                            PaymentCommitment.objects.create(
                                commitment_deposit=payment.commitment_deposit,
                                payment_type=payment_type_obj,
                                is_guide=False,
                                currently_paid=payment.amount * -1,
                                payment_date=payment.payment_date,
                            )
                            payment.commitment_deposit.save()
                            
                    reconnect_payment_signals()
                
        Payment.objects.bulk_update(payments_to_return, ['reject', 'reject_date'], batch_size=100)
        Invoice.objects.bulk_update(invoices_to_update_rejection, ['reject'], batch_size=100)
        
        return_instances = Payment.objects.filter(id__in=return_payments)
        # La gestio d'impagats es crea amb els pagaments que marca el frontal, pero
        # nomes poden ser-hi els d'aquesta devolucio i els que no estiguin ja en una
        # gestio oberta: si es carreguen diversos fitxers seguits sense recarregar la
        # pagina, la seleccio del fitxer anterior hi pot arribar arrossegada i la
        # gestio nova sortia acumulada (veure SEPAReturnSetup.vue::getRejections).
        claim_instances = Payment.objects.filter(id__in=claim_payments)
        if payments_to_return_ids:
            claim_instances = claim_instances.filter(id__in=payments_to_return_ids)
        claim_request_open_tokens = list(ConfigProject.objects.filter(
            token__in=['claim_request_status_pending_token', 'claim_request_status_accepted_token']
        ).values_list('value', flat=True))
        if claim_request_open_tokens:
            claim_instances = claim_instances.exclude(
                claim_requests__claim_request__status__token__in=claim_request_open_tokens
            ).distinct()
        invoice_reject_instance = Invoice.objects.filter(id=invoice_reject)
        if invoice_reject_instance.exists():
            invoice_reject_instance.update(reject=reject)
            return_instances = invoice_reject_instance.first().payments.all()
        return_instances = return_instances.filter(id__in=returned_payment_ids)
        processed_invoice_ids = set()
        for return_instance in return_instances:
            try:
                invoice = return_instance.invoice
                if not invoice:
                    continue
                if invoice.parent_invoice:
                    while invoice.parent_invoice:
                        invoice = invoice.parent_invoice
                if invoice.id in processed_invoice_ids:
                    continue
                processed_invoice_ids.add(invoice.id)
                new_invoice = invoice_return_charge(invoice, 'RECLAMACIÓ DE SERVEI', reject)
                new_invoice.refresh_from_db()
            except Exception as e:
                import traceback
                print(f"Error in manage_rejection_payments for invoice {invoice.id}: {e}")
                traceback.print_exc()
                raise Exception(f"Error while creating return invoices: {e}")
        
        #TODO: CLAIMS
        
        if claim_instances.exists():
            from claimrequest.serializers.claim_request_save_serializer import generate_claim_id
            
            default_template = ClaimRequestTemplate.objects.get(is_default=True)
            
            claim_request = ClaimRequest.objects.create(
                token=generate_claim_id(),
                status=ClaimRequestStatus.objects.get(is_default=True),
                template=default_template,
                user=request.user,
            )
            
            for payment in claim_instances:
                contract = None
                if payment.invoice:
                    contract = payment.invoice.contract
                elif payment.commitment_deposit:
                    contract = payment.commitment_deposit.contract
                ClaimRequestPayment.objects.create(
                    claim_request=claim_request,
                    payment=payment,
                    contract=contract,
                )
        
        
        payments_data = []
        for payment in payments_to_return:
            contract = None
            if payment.contract:
                contract = payment.contract
            if payment.invoice:
                if payment.invoice.contract:
                    contract = payment.invoice.contract
                elif payment.invoice.contract_request:
                    try:
                        contract = Contract.objects.get(contract_request=payment.invoice.contract_request)
                    except Exception as e:
                        print("Error getting contract from contract_request: ", e)
                        contract = None
                elif payment.invoice.contract_termination:
                    contract = payment.invoice.contract_termination.contract
            if payment.commitment_deposit:
                contract = payment.commitment_deposit.contract
            payments_data.append({
                "not_found": False,
                "skip_return": True,
                "holder_name": payment.customer_final,
                "holder_iban": payment.customer_token_final,
                "client_id": None,
                "payment_date": payment.payment_date,
                "amount": payment.amount,
                "motive_id": payment.reject.id if payment.reject else None,
                "motive": payment.reject.name if payment.reject else None,
                "rjt_dt": payment.reject_date,
                "contract": contract.token if contract else None,
                "contract_id": contract.id if contract else None,
                "payment_id": payment.id,
                "payment_token": payment.token,
                "invoice": payment.invoice.serie_final if payment.invoice else None,
                "commitment_deposit": payment.commitment_deposit.token if payment.commitment_deposit else None,
                "holder": None,
                "prev_status": payment.status.name,
                "prev_status_color": payment.status.color,
            })
        
        
        return Response({"rejections": payments_data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='manual-payment')
    def manual_payment(self, request):
        user = request.user
        data = request.data
        payment_id = data.get('id')
        payment_date = data.get('payment_date')
        payment_method = data.get('payment_method', None)
        is_piggy_contract = data.get('is_piggy_contract', False)
        amount = data.get('amount', None)
        
        print("is_piggy_contract: ", is_piggy_contract)
        
        payment = Payment.objects.get(id=payment_id)
        try:
            pay_method = PaymentType.objects.get(id=payment_method)
        except:
            pay_method = PaymentType.objects.get(token=payment.payment_type_token)
        paid_status_token = ConfigProject.objects.get(token='payment_status_paid_token').value
        status_cancelled_token = ConfigProject.objects.get(token='payment_status_cancelled_token').value
        used_token = status_cancelled_token if payment.invoice and payment.invoice.return_token else paid_status_token
        
        if amount == None:
            amount = payment.amount
        
        if amount and float(amount) > 0:
            if payment.invoice or payment.commitment_deposit:
                contract = None
                if payment.invoice:
                    if payment.invoice.contract:
                        contract = payment.invoice.contract
                    elif payment.invoice.contract_termination:
                        contract = payment.invoice.contract_termination.contract
                    """ elif payment.invoice.contract_request:
                        try:
                            contract = Contract.objects.get(contract_request=payment.invoice.contract_request)
                        except Exception as e:
                            print(e)
                            contract = None """
                    # CONTRACT REQUEST NOW WORKS WITH PERSON PIGGY BANK
                elif payment.commitment_deposit:
                    contract = payment.commitment_deposit.contract
                
                if contract and contract.piggy_bank and pay_method.token == 'BALANCE':
                    try:
                        piggy_bank = contract.piggy_bank
                        piggy_bank.amount = float(piggy_bank.amount) - float(amount)
                        if piggy_bank.amount < 0:
                            piggy_bank.amount = 0
                        piggy_bank.save()
                        PiggyBankMovement.objects.create(
                            token=generate_token(PiggyBankMovement),
                            piggy_bank=piggy_bank,
                            amount=float(amount),
                            is_positive=False,
                            movement_date=payment_date,
                            payment=payment,
                        )
                    except Exception as e:
                        print(e)
                elif payment.invoice and (payment.invoice.connection_request or payment.invoice.contract_request) and pay_method.token == 'BALANCE':
                    person = payment.invoice.connection_request.person if payment.invoice.connection_request else payment.invoice.contract_request.person if payment.invoice.contract_request else None
                    print("person: ", person)
                    if person and person.piggy_bank:
                        print("piggy_bank: ", person.piggy_bank)
                        try:
                            print("piggy_bank: ", person.piggy_bank)
                            piggy_bank = person.piggy_bank
                            piggy_bank.amount = float(piggy_bank.amount) - float(amount)
                            print("piggy_bank.amount: ", piggy_bank.amount)
                            if piggy_bank.amount < 0:
                                piggy_bank.amount = 0
                            piggy_bank.save()
                            print("piggy_bank saved: ", piggy_bank)
                            PersonPiggyBankMovement.objects.create(
                                token=generate_token(PersonPiggyBankMovement),
                                person_piggy_bank=piggy_bank,
                                amount=float(amount),
                                is_positive=False,
                                movement_date=payment_date,
                                payment=payment,
                            )
                        except Exception as e:
                            print(e)
            else:
                raise Exception("Piggy bank not found for manual payment")
        
        og_status = payment.status
        payment.status = PaymentStatus.objects.get(token=used_token)
        payment.payment_type = pay_method.name
        payment.payment_type_token = pay_method.token
        payment.payment_date = payment_date
        payment.paid_at = payment_date
        payment.save()
        payment.refresh_from_db()
        paid_status = PaymentStatus.objects.get(token=paid_status_token)
        if payment.movements.count() == 0 or payment.movements.order_by('-movement_date').first().movement_date != payment.payment_date:
            new_status = paid_status
            payment.status = og_status
            log_payment_status(payment, new_status, user, payment.payment_date, payment.payment_type_token)
            generate_payment_movement(
                payment, new_status, 
                payment.payment_date, payment.payment_type_token, 
                payment.payment_bank, user,
                None, 
                payment.remittances.filter(sent_at__isnull=False).order_by('-sent_at').first()
                )
        if payment.invoice:
            disconnect_payment_signals()
            payment.invoice.payment_type_final = pay_method.name
            payment.invoice.payment_type_token_final = pay_method.token
            payment.invoice.save()
            reconnect_payment_signals()
        serialized_invoices = PaymentSerializer(payment)
        return Response({"payment": serialized_invoices.data}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'], url_path='sii-invoices')
    def manage_claim_payments(self, request):
        data = request.data
        sii_invoices = get_sii_invoices(data)
        serialized_invoices = InvoiceMinimalSerializer(sii_invoices, many=True)
        return Response({"invoices": serialized_invoices.data}, status=status.HTTP_200_OK)
        
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
            group_permissions = PermissionManager.get_model_group_permissions(group, 'payment')
            return Response(group_permissions, status=status.HTTP_200_OK)
        permissions = PermissionManager.get_model_permissions(request.user, 'payment', 'billing')
        return Response(permissions, status=status.HTTP_200_OK)
        
    @action(detail=True, methods=['post'], url_path='regenerate-pdf')
    def regenerate_pdf(self, request, pk=None):
        from billing.utils.payment_pdf_service import generate_report_payment_pdf
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        import threading
        import uuid
        import traceback

        payment = self.get_object()
        
        # Actualitzem la data si es rep pel paràmetre 'date'
        date_param = request.query_params.get('date')
        if date_param:
            try:
                # S'espera format YYYY-MM-DD
                new_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                payment.due_date = new_date
                payment.payment_date = new_date
                payment.save()
            except (ValueError, TypeError):
                pass

        try:
            document, signed_pdf_buffer = generate_report_payment_pdf(payment, request)
            payment.document = document
            payment._skip_signal = True
            payment.save()
            
            # Save a temporary copy for the frontend to download (pattern that works for the user due to CORS)
            now_date = timezone.now().date()
            # Simplifiquem el nom del fitxer per evitar caràcters estranys del token
            safe_token = payment.token.replace('/', '').replace(' ', '_')
            temp_filename = f"{now_date.strftime('%m%d')}_{safe_token}_{uuid.uuid4().hex[:6]}.pdf"
            temp_rel_path = f"tmp/payment_docs/{temp_filename}"
            
            signed_pdf_buffer.seek(0)
            saved_path = default_storage.save(temp_rel_path, ContentFile(signed_pdf_buffer.getvalue()))
            file_url = request.build_absolute_uri(default_storage.url(saved_path))

            # Helper to delete file after some time
            def _delete_later(path: str, delay_seconds: int = 60) -> None:
                def _run():
                    try:
                        default_storage.delete(path)
                    except Exception:
                        pass
                t = threading.Timer(delay_seconds, _run)
                t.daemon = True
                t.start()

            _delete_later(saved_path)

            return Response({"pdf_url": file_url}, status=status.HTTP_200_OK)
        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_permissions(self):
        if self.action == 'permissions':
            return [IsAuthenticated()]
        return super().get_permissions()