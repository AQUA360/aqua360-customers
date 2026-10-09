import threading
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import FileResponse, JsonResponse
from django.core.files.base import ContentFile
from rest_framework.views import APIView, Response
from django.conf import settings
from io import BytesIO
import re
import base64
from xhtml2pdf import pisa
from datetime import datetime, timedelta
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import GeneralPayment, GeneralPaymentSepaDocument, Payment, Invoice
from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject
from coredata.serializers import AddressSerializer, PersonCardSerializer, PersonSerializer
from documentmanager.utils.sign_certificate_service import sign_pdf
from billing.utils.barcode_service import generate_barcode
from service.serializers.company_serializer import CompanySerializer
from service.utils.exploitation_logo import exploitation_logo_source

from documentmanager.utils.main_utils import upload_document

class GeneratePaymentDocDownloadViewSet(APIView):
  permission_classes = [IsAuthenticated] #Since it's a view that shows a document, no further permissions are needed
  queryset = Invoice.objects.all().order_by('-created_at')
  def get(self, request, id, *args, **kwargs):
    
    payment = Payment.objects.get(id=id)
    payment_date = request.GET.get('date', None)
    invoice = None
    commitment_deposit = None
    contract = None
    if payment.invoice:
        invoice = payment.invoice
        contract = invoice.contract
    if payment.commitment_deposit:
        commitment_deposit = payment.commitment_deposit
        contract = commitment_deposit.contract
    barcode = None
    exploitation = invoice.exploitation if invoice else commitment_deposit.invoices.first().exploitation
    company = CompanySerializer(exploitation.company,context={'request': request}).data
    logo = company['logo']
    if logo and not logo.startswith('http'):
        logo = request.build_absolute_uri(logo)
        logo = logo.replace('https', 'http')
    
    
    domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''
    exploitation_image = exploitation_logo_source(exploitation)
    now_date = datetime.now().date()
    tomorrow = now_date + timedelta(days=2) if not payment_date else datetime.strptime(payment_date, '%Y-%m-%d').date()
    # Adjust if falls on weekend
    if not payment_date:
        while tomorrow.weekday() >= 5:  
            tomorrow += timedelta(days=1)
    #ident = payment.due_date.strftime("%d%m%y") if payment.due_date else "000000"
    ident = tomorrow.strftime("%d%m%y")
    barcode_data = {
        'reference': invoice.token if invoice else payment.token if len(payment.token) == 11 else payment.token[:-2],
        'total_final': payment.amount,
        'company': exploitation.company,
        'ident': ident,
    }
    from billing.utils.barcode_service import generate_barcode, get_barcode_values
    barcode_values = get_barcode_values(barcode_data)
    barcode = generate_barcode(barcode_data, True)
    if barcode:
        barcode_base64 = base64.b64encode(barcode.getvalue()).decode('utf-8')

    
    main_color = "#074df0"
    secondary_color = "#ffffff"
    try:
        main_color = ConfigProject.objects.get(token='invoice_main_color').value
        secondary_color = ConfigProject.objects.get(token='invoice_secondary_color').value
    except:
        pass
    
    clean_sender = str(int(re.sub(r'[^0-9]', '', company['vat'] or ''))).zfill(8)
    payment_type_token = payment.payment_type_token
    
    company_bank = exploitation.company.company_banks.filter(is_default=True, is_active=True).first()
    if not company_bank:
        company_bank = exploitation.company.company_banks.filter(is_active=True).first()
    
    company_iban = company_bank.iban if company_bank else None
    company_swift = company_bank.swift if company_bank else None
    print('payment_type_token', payment_type_token)

    is_returned = False
    try:
        returned_status_token = ConfigProject.objects.filter(token='payment_status_returned_token').first()
        is_returned = bool(
            returned_status_token
            and payment.status
            and payment.status.token == returned_status_token.value
        )
    except Exception:
        is_returned = False

    # Render HTML content
    html_content = render_to_string('payment_doc_template.html', 
                                    {'invoice': invoice if invoice else commitment_deposit, 'barcode': barcode_base64, 
                                     'barcode_values': barcode_values,
                                     'contract': contract,
                                     'now_date': tomorrow, 'company': company,
                                     'reference': invoice.token if invoice else commitment_deposit.token, 'ident': ident,
                                     'sender': clean_sender, 
                                     'exploitation_image': exploitation_image, 
                                     'main_color': main_color,
                                     'secondary_color': secondary_color,
                                     'logo': logo, 'payment_date': payment.payment_date,
                                     'payment_amount': payment.amount,
                                     'due_date': payment.due_date,
                                     'payment_type_token': payment_type_token,
                                     'company_iban': company_iban,
                                     'company_swift': company_swift,
                                     'client_iban': payment.payment_bank,
                                     'is_returned': is_returned,
                                     })
    pdf_buffer = BytesIO()

    # Generate PDF from HTML
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        return JsonResponse({"error": "PDF generation failed"}, status=500)

    #SIGNATURE
    signed_pdf_buffer = sign_pdf(pdf_buffer, company, '', '')

    # Prepare PDF filename
    pdf_filename = f"{now_date.strftime('%m%d')}_{invoice.serie_final.replace('/','') if invoice else commitment_deposit.token.replace('/','')}.pdf"
    
    # Reset buffer position to beginning
    signed_pdf_buffer.seek(0)
    
    temp_rel_path = f"tmp/payment_docs/{pdf_filename}"
    saved_path = default_storage.save(temp_rel_path, ContentFile(signed_pdf_buffer.getvalue()))
    file_url = request.build_absolute_uri(default_storage.url(saved_path))

    def _delete_later(path: str, delay_seconds: int = 100) -> None:
        def _run():
            try:
                default_storage.delete(path)
            except Exception:
                pass
        t = threading.Timer(delay_seconds, _run)
        t.daemon = True
        t.start()

    _delete_later(saved_path, delay_seconds=20)
    
    return JsonResponse({"pdf_url": file_url})