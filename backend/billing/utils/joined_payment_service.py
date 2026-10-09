

import base64
from io import BytesIO
import os
import re
from decouple import config
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.template.loader import render_to_string
from coredata.utils.pdf_utils import add_watermark_to_pdf
from xhtml2pdf import pisa
from billing.models import JoinedPayment, Payment, PaymentStatus
from billing.serializers.payment_serializer import PaymentListSerializer
from billing.utils.barcode_service import generate_barcode
from billing.utils.payment_service import disconnect_payment_signals, generate_payment_movement, log_payment_status, reconnect_payment_signals
from contract.models import Contract, PaymentType
from contract.serializers.contract_serializer import ContractMinimalListSerializer
from coredata.models import ConfigProject, Person
from coredata.serializers import PersonMinimalSerializer
from rest_framework.response import Response
from rest_framework import status

from documentmanager.utils.alfresco_service import upload_document
from documentmanager.utils.sign_certificate_service import sign_pdf
from logger.models import LogJoinedPaymentStatusChange
from service.models import Company, Exploitation
from service.serializers.company_serializer import CompanySerializer
from service.utils.exploitation_logo import exploitation_logo_source
from statistics.utils.report_service import delete_file_later

def get_pending_client_data(data):
    contract_id = data.get('contract', None)
    person_id = data.get('person', None)
    
    if contract_id and person_id:
        raise Exception("Only one of contract_id or person_id can be provided")
    if not contract_id and not person_id:
        raise Exception("Either contract_id or person_id must be provided")
    
    
    payment_status_tokens_config = [
        "payment_status_returned_token",
        "payment_status_pending_token",
        "payment_status_sent_token",
        "payment_status_expired_token",
        "payment_status_endowment_token",
        "payment_status_irrecoverable_token"
    ]
    joined_payment_status_tokens_config = [
        "joined_payment_status_paid_token",
        "joined_payment_status_pending_token",
        "joined_payment_status_expired_token"
    ]
    
    payment_status_tokens = ConfigProject.objects.filter(token__in=payment_status_tokens_config).values_list('value', flat=True)
    joined_payment_status_tokens = ConfigProject.objects.filter(token__in=joined_payment_status_tokens_config).values_list('value', flat=True)
    
    contract = None
    person = None
    payments = []
    if contract_id:
        contract = Contract.objects.get(id=contract_id)
        payments = Payment.objects.filter(
            Q(contract__id=contract_id) | 
            Q(commitment_deposit__contract__id=contract_id) | 
            Q(invoice__contract_request__contract__id=contract_id) |
            Q(invoice__contract_termination__contract__id=contract_id)
        ).exclude(joined_payments__status__token__in=joined_payment_status_tokens).distinct()
    elif person_id:
        person = Person.objects.get(id=person_id)
        print("person: ", person)
        person_name_variations = [
            f"{person.name} {person.surname if person.surname else ''}",
            f"{person.name}{person.surname if person.surname else ''}",
            f"{person.name}{person.surname}" if person.surname else person.name,
        ]
        print("person_name_variations: ", person_name_variations)
        payments = Payment.objects.filter(
            Q(person__id=person_id) | 
            Q(invoice__customer_token_final=person.token, invoice__customer_final__in=person_name_variations) |
            Q(commitment_deposit__customer_token_final=person.token, commitment_deposit__customer_final__in=person_name_variations)
        ).exclude(joined_payments__status__token__in=joined_payment_status_tokens).distinct()
    
    pending_payments = payments.filter(
            status__token__in=payment_status_tokens,
            amount__gt=0,
            is_active=True
        ).exclude(remittances__id__isnull=False, remittances__sent_at__isnull=True).order_by('invoice__serie_final', 'commitment_deposit__token', '-due_date')
    
    total_pending = pending_payments.aggregate(total=Sum('amount'))['total']
    total_pending_invoices = pending_payments.filter(invoice__isnull=False).aggregate(total=Sum('amount'))['total']
    total_pending_commitments = pending_payments.filter(commitment_deposit__isnull=False).aggregate(total=Sum('amount'))['total']
    
    
    return {
        'contract': ContractMinimalListSerializer(contract).data if contract else None,
        'person': PersonMinimalSerializer(person).data if person else None,
        'pending_payments': PaymentListSerializer(pending_payments, many=True).data,
        'total_pending': total_pending,
        'total_pending_invoices': total_pending_invoices,
        'total_pending_commitments': total_pending_commitments
    }

def register_joined_payment_log(joined_payment, previous_status, current_status, observation, user):
    LogJoinedPaymentStatusChange.objects.create(
        object=joined_payment,
        previous_status=previous_status,
        current_status=current_status,
        observation=observation,
        user=user
    )


def generate_joined_payment_id(used_token, count = 1):
    from django.db.models import Max
    
    max_token = JoinedPayment.objects.filter(
        token__startswith=used_token
    ).aggregate(
        max_token=Max('token')
    )['max_token']
    
    if max_token:
        try:
            current_num = int(max_token[len(used_token):])
            next_num = current_num + count
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    
    ident = str(next_num).zfill(9)
    new_token = used_token + ident
    
    max_attempts = 100
    attempts = 0
    while JoinedPayment.objects.filter(token=new_token).exists() and attempts < max_attempts:
        next_num += 1
        ident = str(next_num).zfill(9)
        new_token = used_token + ident
        attempts += 1
    
    if attempts >= max_attempts:
        raise Exception(f"Unable to generate unique payment ID after {max_attempts} attempts")
    
    return new_token

def mark_payments_as_paid(joined_payment, user, payment_origin = None):
    
    payments = joined_payment.payments.all()
    payment_paid_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token="payment_status_paid_token").value)
    
    for payment in payments:
        og_status = payment.status
        payment.status = payment_paid_status
        payment.payment_type = joined_payment.payment_type.name
        payment.payment_type_token = joined_payment.payment_type.token
        payment.payment_date = joined_payment.payment_date
        payment.paid_at = joined_payment.payment_date
        payment.payment_origin_choice = payment_origin
        payment.save()
        
        if payment.movements.count() == 0 or payment.movements.order_by('-movement_date').first().movement_date != payment.payment_date:
            new_status = payment.status
            payment.status = og_status
            # log_payment_status(payment, new_status, user, payment.payment_date, payment.payment_type_token)
            generate_payment_movement(
                payment, new_status, 
                payment.payment_date, payment.payment_type_token, 
                payment.payment_bank, user,
                None, 
                None
            )
        
        if payment.invoice:
            disconnect_payment_signals()
            payment.invoice.payment_type_final = joined_payment.payment_type.name
            payment.invoice.payment_type_token_final = joined_payment.payment_type.token
            payment.invoice.save()
            reconnect_payment_signals()

def generate_report_joined_payment_pdf(joined_payment, user, request = None):
    try:
        contract = joined_payment.contract if joined_payment else Contract.objects.filter(id=request.data.get('contract_id', None)).first()
        payments = joined_payment.payments.all().order_by('amount') if joined_payment else Payment.objects.filter(id__in=request.data.get('payments_data', [])).order_by('amount')
        payment_type = joined_payment.payment_type if joined_payment else PaymentType.objects.get(id=request.data.get('payment_method_id', None))
        
        if contract:
            exploitation = contract.supply_point_default.connection.exploitation
        else:
            payment_exploitations = payments.filter(invoice__isnull=False).values_list('invoice__exploitation', flat=True)
            if payment_exploitations.count() > 0:
                exploitation = Exploitation.objects.get(id=payment_exploitations[0])
            else:
                payment_exploitations = payments.filter(commitment_deposit__isnull=False).values_list('commitment_deposit__invoices__exploitation', flat=True)
                if payment_exploitations.count() > 0:
                    exploitation = Exploitation.objects.get(id=payment_exploitations[0])
                else:
                    exploitation = None.objects.get(id=payment_exploitations[0])
                


        contract = None
        total = joined_payment.total_final if joined_payment else payments.aggregate(total=Sum('amount'))['total']
        title = f"00000000000"
        
        barcode = None
        barcode_base64 = None
        
        company = exploitation.company if exploitation else Company.objects.get(vat=ConfigProject.objects.get(token="main_company_token").value)
        
        ident = joined_payment.due_date.strftime("%d%m%y") if joined_payment else "000000"
        barcode_data = {
            'reference': joined_payment.token if joined_payment else "00000000000",
            'total_final': total if joined_payment else 0,
            'company': company,
            'ident': ident,
        }
        barcode = generate_barcode(barcode_data)
        if barcode:
            barcode_base64 = base64.b64encode(barcode.getvalue()).decode('utf-8')
        
        from billing.utils.barcode_service import get_barcode_values
        barcode_values = get_barcode_values(barcode_data)
        
        file_template = 'grouped_payment_template.html'

        main_color = "#074df0"
        secondary_color = "#ffffff"
        try:
            main_color = ConfigProject.objects.get(token='invoice_main_color').value
            secondary_color = ConfigProject.objects.get(token='invoice_secondary_color').value
        except:
            pass
        
        
        company_data = CompanySerializer(company, context={'request': request}).data
        
        logo = None
        if exploitation and exploitation.company.logo:
            try:
                logo = exploitation.company.logo.path
                if not os.path.exists(logo):
                    logo = None
            except:
                logo = None
        
        if not logo:
            logo = company_data['logo']
            if logo and not logo.startswith('http') and request:
                logo = request.build_absolute_uri(logo)
            elif logo and not logo.startswith('http'):
                domain = settings.DOMAIN_MEDIA or ""
                logo = f"{domain}{logo}"
        
        if logo:
            logo = logo.replace('https', 'http')
        
        domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''
        exploitation_image = exploitation_logo_source(exploitation)
        
        clean_sender = str(int(re.sub(r'[^0-9]', '', company_data['vat'] or ''))).zfill(8)
        
        payment_type_token = payment_type.token
        
        company_bank = exploitation.company.company_banks.filter(is_default=True, is_active=True).first()
        if not company_bank:
            company_bank = exploitation.company.company_banks.filter(is_active=True).first()
        
        company_iban = company_bank.iban if company_bank else None
        company_swift = company_bank.swift if company_bank else None
        
        

        context = {
            'object': joined_payment,
            'payments': payments,
            'company': company_data,
            'contract': contract,
            'barcode': barcode_base64,
            'title': title,
            'barcode_values': barcode_values,
            'payment_amount': total,
            'main_color': main_color,
            'secondary_color': secondary_color,
            'logo': logo,
            'exploitation_image': exploitation_image,
            'sender': clean_sender,
            'reference': joined_payment.token if joined_payment else "00000000000",
            'ident': ident,
            'payment_type_token': payment_type_token,
            'company_iban': company_iban,
            'company_swift': company_swift,
        }
        
        html_rendered = render_to_string(file_template, context)
            
        pdf_buffer = BytesIO()

        pisa_status = pisa.CreatePDF(html_rendered, dest=pdf_buffer)
        if pisa_status.err:
            raise Exception("PDF generation failed")
        
        test_watermark_path = None
        
        if config('ENV', default='-').upper() == 'TEST' or config('ENV', default='-').upper() == 'LOCAL':
            try:
                test_watermark_path = os.path.join("config", "assets", "test-watermark.png")
            except Exception as e:
                print(f"Error en afegir el fons: {str(e)}")
        
        if not joined_payment:
            watermark_path = os.path.join("config", "assets", "watermark.png")  # Path to watermark
            try:
                if test_watermark_path:
                    pdf_buffer = add_watermark_to_pdf(pdf_buffer, test_watermark_path, opacity=0.1)
                else:
                    pdf_buffer = add_watermark_to_pdf(pdf_buffer, watermark_path)
            except Exception as e:
                error_msg = f"Error en afegir watermark o guardar PDF temporal: {str(e)}"
                print(error_msg)
                raise Exception(error_msg)
        
        #SIGNATURE
        signed_pdf_buffer = sign_pdf(
            pdf_buffer, 
            company, 
            title, 
            'FACTURA'
            )

        pdf_filename = f"{contract.token.replace('/', '') if contract else joined_payment.person.token.replace('/', '') if joined_payment else '00000000000'}_{joined_payment.token if joined_payment else 'XXX'}.pdf"
        
        signed_pdf_buffer.seek(0)
    
        temp_rel_path = f"tmp/payment_docs/{pdf_filename}"
        saved_path = default_storage.save(temp_rel_path, ContentFile(signed_pdf_buffer.getvalue()))
        file_url = request.build_absolute_uri(default_storage.url(saved_path))

        delete_file_later(saved_path, delay_seconds=20)
        
        return JsonResponse({"file_url": file_url}, status=status.HTTP_200_OK)
    except Exception as e:
        raise Exception(f"Error generating report: {str(e)}")