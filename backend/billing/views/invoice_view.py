import datetime
import calendar
from rest_framework.decorators import action
from rest_framework import viewsets, status
from django.core.files.storage import default_storage
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from django.core.files.base import ContentFile
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.contrib.auth.models import Group
import zipfile
import time
import io
from billing.utils.payment_service import log_invoice_status
from billing.utils.invoice_service import generate_payment_id
from django.utils.translation import gettext as _
from auth.permissions import PermissionManager
from billing.filter.invoice_filter import InvoiceFilter
from billing.models import Invoice, InvoiceLog, InvoiceStatus, InvoiceSuppressionReason, Payment, PaymentStatus, PaymentType, RejectMotive, PaymentMovement
from billing.serializers.invoice_serializer import InvoiceFullSerializer, InvoiceLogSerializer, InvoiceMinimalSerializer
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals, log_payment_status, generate_payment_movement
from billing.utils.invoice_service import get_electronic_invoices_data, return_invoice, log_invoice_data_change, change_status_logger
from billing.utils.invoice_list_queryset import invoice_list_queryset
from billing.utils.invoice_suppression_service import suppress_invoice
from coredata.models import ConfigProject, PersonAddress, PersonPiggyBankMovement
from contract.models import PiggyBankMovement, Contract
from coredata.utils.name_utils import generate_token
from billing.views.epayment_document_generate_view import generate_xml
from statistics.utils.report_service import delete_file_later

class InvoiceViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = Invoice.objects.all().filter(is_active=True).order_by('-issue_date', '-created_at','status__position')
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = InvoiceFilter
  search_fields = ['token','title_final', 'number', 'contract__token', 'contract_request__token', 'customer_final', 'customer_token_final', 'serie_final', 'payment_bank_final' ]
  ordering_fields = ['token','name','origin','customer_final','total_final','status', 'customer_token_final', 'left_to_pay', "issue_date", "due_date", "payment_type"]
  
  def get_queryset(self):
    if self.action == 'list':
      queryset = invoice_list_queryset()
    else:
      queryset = super().get_queryset()
    if self.action == 'list' and 'is_excluded' not in self.request.query_params:
        return queryset.filter(is_excluded=False)
    return queryset
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return InvoiceMinimalSerializer
        elif self.action == 'retrieve':
            return InvoiceFullSerializer
    return InvoiceFullSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
   
  @action(detail=True, methods=['put'], url_path='return')
  def return_invoice(self, request, pk=None):
    invoice = self.get_object()
    user = request.user if request else None
    reason_id = request.data.get('reason_id')
    payment_type_id = request.data.get('payment_type_id')
    return_paid_total = request.data.get('return_paid_total', False)
    return_paid_total_balance = request.data.get('return_paid_total_balance', False)
    return_paid_total_balance_type = request.data.get('return_paid_total_balance_type', False)
    return_paid_total_balance_type_iban = request.data.get('return_paid_total_balance_type_iban', False)
    
    reason = InvoiceSuppressionReason.objects.get(id=reason_id)
    suppress_invoice(
        invoice, user, reason=reason, payment_type_id=payment_type_id,
        return_paid_total=return_paid_total,
        return_paid_total_balance=return_paid_total_balance,
        return_paid_total_balance_type=return_paid_total_balance_type,
        return_paid_total_balance_type_iban=return_paid_total_balance_type_iban,
    )
    
    return Response({'message': 'Invoice returned successfully'}, status=status.HTTP_200_OK)
   
  @action(detail=True, methods=['put'], url_path='change-payment-method')
  def change_payment_method_invoice(self, request, pk=None):
    invoice = self.get_object()
    user = request.user if request else None
    payment_type_final = request.data.get('payment_type_final', None)
    payment_bank_final = request.data.get('payment_bank_final', None)
    
    payment_type = PaymentType.objects.get(id=payment_type_final)
    invoice_status_paid_token = ConfigProject.objects.get(token='invoice_status_paid_token').value
    payment_status_paid_token = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)

    disconnect_payment_signals()
    
    log_invoice_data_change(user, invoice, None, payment_type.name, payment_bank_final)

    invoice.payment_bank_final = payment_bank_final
    invoice.payment_type_final = payment_type.name
    invoice.payment_type_token_final = payment_type.token
    # invoice.payment_type = payment_type
    invoice.save()
    
    payments = invoice.payments.all()
    if invoice.status.token != invoice_status_paid_token:
        payments = payments.exclude(status__token=payment_status_paid_token).distinct()
    else:
        payments = payments.exclude(payment_type_token="BALANCE").distinct()
    payments.update(
        payment_type=payment_type.name, 
        payment_type_token=payment_type.token, 
        payment_bank=payment_bank_final)
    reconnect_payment_signals()
    return Response({'message': 'Invoice updated successfully'}, status=status.HTTP_200_OK)
   
  @action(detail=True, methods=['put'], url_path='change-dates')
  def change_date_invoice(self, request, pk=None):
    invoice = self.get_object()
    user = request.user if request else None
    due_date = request.data.get('due_date', None)
    send_date = request.data.get('send_date', None)
    
    disconnect_payment_signals()
    
    remittance_date = invoice.contract.remittance_date if invoice.contract else invoice.contract_request.remittance_date if invoice.contract_request else None
    send_date_parsed = self._parse_date(send_date)
    due_date_parsed = self._parse_date(due_date)
    
    if remittance_date:
        last_day_of_month = calendar.monthrange(due_date_parsed.year, due_date_parsed.month)[1]
        last_day_of_month_send = calendar.monthrange(send_date_parsed.year, send_date_parsed.month)[1]
        remittance_day = min(remittance_date, last_day_of_month)
        remittance_day_send = min(remittance_date, last_day_of_month_send)
        if remittance_day > due_date_parsed.day:
            due_date = datetime.date(due_date_parsed.year, due_date_parsed.month, remittance_day)
        if send_date_parsed and send_date_parsed.day < remittance_day_send:
            send_date = datetime.date(send_date_parsed.year, send_date_parsed.month, remittance_day_send)
    
    if invoice.due_date != due_date:
        InvoiceLog.objects.create(
            invoice=invoice,
            user=user,
            operation_token="change_due_date",
            field_name="due_date",
            old_value=invoice.due_date,
            new_value=due_date,
        )
    if invoice.send_at != send_date:
        InvoiceLog.objects.create(
            invoice=invoice,
            user=user,
            operation_token="change_send_date",
            field_name="send_date",
            old_value=invoice.send_at,
            new_value=send_date,
        )
    
    invoice.due_date = due_date
    invoice.send_at = send_date
    invoice.save()
    payments = invoice.payments.all()
    payments.update(
        due_date=due_date,
    )

    reconnect_payment_signals()
    return Response({'message': 'Invoice updated successfully'}, status=status.HTTP_200_OK)
  
  @action(detail=True, methods=['put'], url_path='change-address')
  def change_address_invoice(self, request, pk=None):
    invoice = self.get_object()
    user = request.user if request else None
    address_final = request.data.get('address_final', None)
    accounting_office_final = request.data.get('accounting_office_final', None)
    managing_body_final = request.data.get('managing_body_final', None)
    processing_unit_final = request.data.get('processing_unit_final', None)
    
    try:
        address = PersonAddress.objects.get(id=address_final)
    except Exception as e:
        address = None
    
    if accounting_office_final:
        invoice.accounting_office_final = accounting_office_final
    if managing_body_final:
        invoice.managing_body_final = managing_body_final
    if processing_unit_final:
        invoice.processing_unit_final = processing_unit_final
    
    if address:
        
        log_invoice_data_change(user, invoice, str(address.address), None)
        invoice.address_final = str(address.address)
        invoice.location_final = f"{address.address.postal_code} {address.address.city.name}, {address.address.province.name} - {address.address.country.iso_code}"
        invoice.postal_code_final = address.address.postal_code if address.address.postal_code else None
        invoice.city_final = address.address.city.name if address.address.city else None
        invoice.province_final = address.address.province.name if address.address.province else None
        invoice.country_final = address.address.country.iso_code if address.address.country else None
    
    disconnect_payment_signals()

    invoice.save()
    
    payments = invoice.payments.all()
    payments.update(
        address_final=invoice.address_final, 
        location_final=invoice.location_final, 
        )
    reconnect_payment_signals()
    return Response({'message': 'Invoice updated successfully'}, status=status.HTTP_200_OK)
  
  @action(detail=True, methods=['put'], url_path='pass-to-pending')
  def pass_to_pending(self, request, pk=None):
        today = timezone.now().date()
        return_date = self._parse_date(request.data.get('return_date'))
        invoice = self.get_object()
        returned = request.data.get('return_reason', None)
        return_all = self._parse_bool(request.data.get('return_all'), False)
        return_sepa_to_piggy = self._parse_bool(request.data.get('return_sepa_to_piggy'), False)
        has_return = bool(returned and returned != '' and returned != 'null')
        
        balance_token = "BALANCE"
        sepa_type = PaymentType.objects.get(token="DIRECT_DEBIT")
        bank_type = PaymentType.objects.get(token="BANK_PAYMENT")
        rejc_reason = None
        if has_return:
            try:
                rejc_reason = RejectMotive.objects.get(id=returned)
            except Exception as e:
                print(e)
        invoice.reject = rejc_reason
        user = request.user if request else None
        # Devolució manual: mateix criteri que SEPA (pagament Retornat; factura Confirmada/Vençuda).
        if has_return:
            disconnect_payment_signals()
            invoice_confirmed_token = ConfigProject.objects.get(token='invoice_status_confirmed_token').value
            invoice_expired_token = ConfigProject.objects.get(token='invoice_status_expired_token').value
            payment_paid_token = ConfigProject.objects.get(token='payment_status_paid_token').value
            payment_return_token = ConfigProject.objects.get(token='payment_status_returned_token').value
            payment_return = PaymentStatus.objects.get(token=payment_return_token)
            invoice_confirmed = InvoiceStatus.objects.get(token=invoice_confirmed_token)
            invoice_expired = InvoiceStatus.objects.get(token=invoice_expired_token)
            invoice_new_status = invoice_confirmed if invoice.due_date > today else invoice_expired
            log_invoice_status(invoice, invoice_new_status, user)
            payments = invoice.payments.all()
            for payment in payments:
                is_balance = payment.payment_type_token == balance_token
                if is_balance and not return_all:
                    continue
                if payment.status.token != payment_paid_token:
                    continue
                payment_invoice = payment.invoice
                refund_to_piggy = is_balance or return_sepa_to_piggy
                if refund_to_piggy:
                    self._refund_payment_to_piggy(payment, payment_invoice, return_date)
                payment.reject = rejc_reason
                payment.reject_date = return_date
                log_payment_status(payment, payment_return, user)
                generate_payment_movement(
                    payment, payment_return, return_date,
                    payment.payment_type_token, payment.payment_bank, user,
                    rejc_reason,
                    payment.remittances.filter(sent_at__isnull=False).order_by('-sent_at').first())
                if is_balance:
                    payment.payment_type = invoice.payment_type_final
                    payment.payment_bank = invoice.payment_bank_final
                    payment.payment_swift = invoice.payment_swift_final
                    payment.payment_token = invoice.payment_token_final
                payment.status = payment_return
                payment.save()
            if return_all:
                invoice.left_to_pay = invoice.total_final
            else:
                total_still_paid = sum(
                    float(payment.amount or 0)
                    for payment in invoice.payments.filter(status__token=payment_paid_token)
                )
                invoice.left_to_pay = float(invoice.total_final or 0) - total_still_paid
            invoice.status = invoice_new_status
            invoice.save()
        elif invoice.due_date < today:
            invoice_expired_token = ConfigProject.objects.get(token='invoice_status_expired_token').value
            payment_expired_token = ConfigProject.objects.get(token='payment_status_expired_token').value
            invoice_expired = InvoiceStatus.objects.get(token=invoice_expired_token)
            payment_expired = PaymentStatus.objects.get(token=payment_expired_token)
            
            payments = invoice.payments.all()
            for payment in payments:
                # if payment.amount == og_left_to_pay or return_all:
                payment.status = payment_expired
                contract = payment.contract
                invoice = payment.invoice
                if payment.payment_type_token == balance_token:
                    if contract and contract.piggy_bank:
                        PiggyBankMovement.objects.create(
                            token=generate_token(PiggyBankMovement),
                            piggy_bank=contract.piggy_bank,
                            amount=payment.amount,
                            is_positive=True,
                            movement_date=timezone.now(),
                            payment=payment,
                        )
                        contract.piggy_bank.amount += payment.amount
                        contract.piggy_bank.save()
                    elif invoice and (invoice.connection_request or invoice.contract_request):
                        person = invoice.connection_request.person if invoice.connection_request else invoice.contract_request.person if invoice.contract_request else None
                        if person and person.piggy_bank:
                            PersonPiggyBankMovement.objects.create(
                                token=generate_token(PersonPiggyBankMovement),
                                person_piggy_bank=person.piggy_bank,
                                amount=payment.amount,
                                is_positive=True,
                                movement_date=timezone.now(),
                                payment=payment,
                            )
                            person.piggy_bank.amount += payment.amount
                            person.piggy_bank.save()
                    payment.payment_type = invoice.payment_type_final
                    payment.payment_bank = invoice.payment_bank_final
                    payment.payment_swift = invoice.payment_swift_final
                    payment.payment_token = invoice.payment_token_final
                
                        
                payment.save()
            disconnect_payment_signals()
            invoice.left_to_pay = invoice.total_final
            invoice.save()
        else:
            disconnect_payment_signals()
            invoice_confirmed_token = ConfigProject.objects.get(token='invoice_status_confirmed_token').value
            payment_pending_token = ConfigProject.objects.get(token='payment_status_pending_token').value
            payment_return_token = ConfigProject.objects.get(token='payment_status_returned_token').value
            payment_return = PaymentStatus.objects.get(token=payment_return_token)
            invoice_confirmed = InvoiceStatus.objects.get(token=invoice_confirmed_token)
            payment_pending = PaymentStatus.objects.get(token=payment_pending_token)
            log_invoice_status(invoice, invoice_confirmed, user)
            payments = invoice.payments.all()
            for payment in payments:
                new_status = payment_pending if not returned or returned == '' or returned == 'null' else payment_return
                contract = payment.contract
                invoice = payment.invoice
                if payment.payment_type_token == balance_token:
                    if contract and contract.piggy_bank:
                        PiggyBankMovement.objects.create(
                            token=generate_token(PiggyBankMovement),
                            piggy_bank=contract.piggy_bank,
                            amount=payment.amount,
                            is_positive=True,
                            movement_date=timezone.now(),
                            payment=payment,
                        )
                        contract.piggy_bank.amount += payment.amount
                        contract.piggy_bank.save()
                    elif invoice and (invoice.connection_request or invoice.contract_request):
                        person = invoice.connection_request.person if invoice.connection_request else invoice.contract_request.person if invoice.contract_request else None
                        if person and person.piggy_bank:
                            PersonPiggyBankMovement.objects.create(
                                token=generate_token(PersonPiggyBankMovement),
                                person_piggy_bank=person.piggy_bank,
                                amount=payment.amount,
                                is_positive=True,
                                movement_date=timezone.now(),
                                payment=payment,
                            )
                            person.piggy_bank.amount += payment.amount
                            person.piggy_bank.save()
                log_payment_status(payment, new_status, user)
                movement_date = timezone.now()
                generate_payment_movement(
                    payment, new_status, movement_date, 
                    payment.payment_type_token, payment.payment_bank, user,
                    rejc_reason, 
                    payment.remittances.filter(sent_at__isnull=False).order_by('-sent_at').first())
                payment.status = new_status
                payment.save()
            invoice.left_to_pay = invoice.total_final
            invoice.status = invoice_confirmed
            invoice.save()
        
        if invoice.payment_type_token_final == balance_token:
            disconnect_payment_signals()
            invoice.payment_type_final = bank_type.name
            invoice.payment_type_token_final = bank_type.token
            contract = None
            if invoice.contract:
                contract = invoice.contract
            if invoice.contract_request:
                try:
                    contract = Contract.objects.get(contract_request=invoice.contract_request)
                except:
                    pass
            if not contract:
                if invoice.person:
                    person_bank = PersonBank.objects.filter(person=invoice.person, is_default=True, is_active=True).first()
                    if not person_bank:
                        person_bank = PersonBank.objects.filter(person=invoice.person, is_active=True).first()
                    if person_bank:
                        invoice.payment_type_final = sepa_type.name
                        invoice.payment_type_token_final = sepa_type.token
                        invoice.payment_bank_final = person_bank.iban
                        invoice.payment_swift_final = person_bank.swift
            else:
                if contract.payment:
                    invoice.payment_type_final = contract.payment.type.name
                    invoice.payment_type_token_final = contract.payment.type.token
                    invoice.payment_bank_final = contract.payment.IBAN.iban if contract.payment.IBAN else None
                    invoice.payment_swift_final = contract.payment.IBAN.swift if contract.payment.IBAN else None
            invoice.save()
            invoice.payments.update(
                payment_type=invoice.payment_type_final,
                payment_type_token=invoice.payment_type_token_final,
                payment_bank=invoice.payment_bank_final,
                payment_swift=invoice.payment_swift_final,
            )
                        
        
        reconnect_payment_signals()
        return Response({'message': 'Invoice passed to pending successfully'}, status=status.HTTP_200_OK)

  @action(detail=True, methods=['get'], url_path='logs')
  def logs(self, request, pk=None):
      try:
          invoice = self.get_object()
          logs = InvoiceLog.objects.filter(invoice=invoice).order_by('-created_at')
          serializer = InvoiceLogSerializer(logs, many=True, context={'request': request})
          return Response(serializer.data, status=status.HTTP_200_OK)
      except Invoice.DoesNotExist:
          return Response(
              {"error": "Invoice not found"}, 
              status=status.HTTP_404_NOT_FOUND
          )

  @action(detail=True, methods=['get'], url_path='general-summary-pdf')
  def general_summary_pdf(self, request, pk=None):
      from billing.utils.general_invoice_summary_service import generate_general_invoice_summary_pdf
      invoice = self.get_object()
      try:
          pdf_bytes, filename = generate_general_invoice_summary_pdf(invoice)
      except ValueError as e:
          return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
      response = HttpResponse(pdf_bytes, content_type='application/pdf')
      response['Content-Disposition'] = f'attachment; filename={filename}'
      response['Access-Control-Expose-Headers'] = 'Content-Disposition'
      return response

  @action(detail=True, methods=['get'], url_path='e-invoice')
  def generate_electronic_invoice(self, request, pk=None):
      try:
          invoice = self.get_object()
          xml_data = generate_xml(None, invoice)
          xml_file_name = f"{invoice.serie_final.replace('/', '_')}_{invoice.id}.xml"
          
          # Create zip file in memory
          zip_buffer = io.BytesIO()
          with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
              zip_file.writestr(xml_file_name, xml_data.encode("utf-8"))
          
          zip_buffer.seek(0)
          zip_file_name = f"{invoice.serie_final.replace('/', '_')}_{invoice.id}.zip"
          zip_file = ContentFile(zip_buffer.read(), name=zip_file_name)
          
          temp_rel_path = f"tmp/einvoice/{zip_file_name}"
          saved_path = default_storage.save(temp_rel_path, zip_file)
          file_url = request.build_absolute_uri(default_storage.url(saved_path))
          delete_file_later(saved_path, delay_seconds=20)
          
          return JsonResponse({"file_url": file_url})
      except Invoice.DoesNotExist:
          return Response(
              {"error": "Invoice not found"}, 
              status=status.HTTP_404_NOT_FOUND
          )

  @action(detail=False, methods=['post'], url_path='get-e-invoice')
  def generate_e_invoice(self, request):
      try:
          
          return Response(get_electronic_invoices_data(request), status=status.HTTP_200_OK)
      except Invoice.DoesNotExist:
          return Response(
              {"error": "Invoice not found"}, 
              status=status.HTTP_404_NOT_FOUND
          )
  
  @action(detail=False, methods=['post'], url_path='invoice-documents')
  def obtain_invoice_documents(self, request):
    try:
        from billing.views.invoice_pdf_view import generate_report_invoice_pdf
        ids = request.data.get('ids', [])
        invoices = Invoice.objects.filter(id__in=ids)
        document_ids = []
        for invoice in invoices:
            if not invoice.invoice_file:
                print(f"invoice {invoice.serie_final} has no invoice file")
                _, doc_id, _ =generate_report_invoice_pdf(invoice)
                document_ids.append(doc_id)
            else:
                document_ids.append(invoice.invoice_file.id)
        return Response({"invoice_file_ids": document_ids}, status=status.HTTP_200_OK)
    except Invoice.DoesNotExist:
        return Response(
            {"error": "Invoice not found"},
            status=status.HTTP_404_NOT_FOUND
        )

  @action(detail=False, methods=['post'], url_path='massive-download')
  def massive_download(self, request):
    from billing.tasks import generate_massive_invoice_download
    excluded_ids = request.data.get('excluded_ids', [])
    in_zip = request.data.get('in_zip', True)

    queryset = Invoice.objects.all().filter(is_active=True)
    if 'is_excluded' not in request.query_params:
        queryset = queryset.filter(is_excluded=False)
    queryset = self.filter_queryset(queryset)
    if excluded_ids:
        queryset = queryset.exclude(id__in=excluded_ids)

    invoice_ids = list(queryset.values_list('id', flat=True).distinct())
    if not invoice_ids:
        return Response({"error": "No invoices found"}, status=status.HTTP_404_NOT_FOUND)

    base_url = request.build_absolute_uri('/')
    task = generate_massive_invoice_download.delay(invoice_ids, base_url, in_zip)
    return Response({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

  @action(detail=True, methods=['post'], url_path='recalculate-smart')
  def recalculate_smart(self, request, pk=None):
    from billing.utils.recalculate_invoice_service import recalculate_invoice_smart
    invoice = self.get_object()
    try:
        new_invoice = recalculate_invoice_smart(invoice.id)
        serializer = InvoiceFullSerializer(new_invoice, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
          group_permissions = PermissionManager.get_model_group_permissions(group, 'invoice')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'invoice', 'billing')
      return Response(permissions, status=status.HTTP_200_OK)
      
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()
  
  def _parse_date(self, date_value):
    """Helper function to parse date from various formats."""
    if date_value is None:
        return datetime.datetime.now().date()
    if isinstance(date_value, datetime.date):
        return date_value
    if isinstance(date_value, str):
        try:
            return datetime.datetime.strptime(date_value, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return datetime.datetime.now().date()
    return datetime.datetime.now().date()

  def _parse_bool(self, value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes', 'on')
    return bool(value)

  def _refund_payment_to_piggy(self, payment, invoice, movement_date):
    contract = payment.contract
    if contract and contract.piggy_bank:
        PiggyBankMovement.objects.create(
            token=generate_token(PiggyBankMovement),
            piggy_bank=contract.piggy_bank,
            amount=payment.amount,
            is_positive=True,
            movement_date=movement_date,
            payment=payment,
        )
        contract.piggy_bank.amount += payment.amount
        contract.piggy_bank.save()
        return
    if invoice and (invoice.connection_request or invoice.contract_request):
        person = (
            invoice.connection_request.person
            if invoice.connection_request
            else invoice.contract_request.person if invoice.contract_request else None
        )
        if person and person.piggy_bank:
            PersonPiggyBankMovement.objects.create(
                token=generate_token(PersonPiggyBankMovement),
                person_piggy_bank=person.piggy_bank,
                amount=payment.amount,
                is_positive=True,
                movement_date=movement_date,
                payment=payment,
            )
            person.piggy_bank.amount += payment.amount
            person.piggy_bank.save()
    