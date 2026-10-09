
import os
import base64
import re
from io import BytesIO
from django.conf import settings
from billing.utils.barcode_service import generate_barcode
from billing.utils.invoice_pdf import hide_iban
from coredata.models import ConfigProject
from documentmanager.utils.main_utils import upload_document
from documentmanager.utils.sign_certificate_service import sign_pdf
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.core.files.base import ContentFile
from xhtml2pdf import pisa
from service.serializers.company_serializer import CompanySerializer
from service.utils.exploitation_logo import exploitation_logo_source

def generate_report_payment_pdf(payment, request = None, limit_date = None):
    from service.models import Exploitation
    from billing.models import CommitmentDeposit, Invoice
    
    try:
        
        exploitation = Exploitation.objects.filter(is_active=True).first()
        payment_object = None
        contract = None
        hiden_iban = None
        total = payment.amount
        title = ''
        
        barcode = None
        barcode_base64 = None
        
        invoice = payment.invoice
        commitment_deposit = payment.commitment_deposit
        
        if invoice:
            payment_object = invoice
            if invoice.exploitation:
                exploitation = invoice.exploitation
            title = invoice.title_final
            if invoice.contract:
                contract = invoice.contract
            elif invoice.contract_request:
                contract = invoice.contract_request
        elif commitment_deposit:
            payment_object = commitment_deposit
            contract = commitment_deposit.contract
            if commitment_deposit.invoices.exists():
                exploitation = commitment_deposit.invoices.first().exploitation
            elif contract:
                if contract.supply_point_default and contract.supply_point_default.connection and contract.supply_point_default.connection.exploitation:
                    exploitation = contract.supply_point_default.connection.exploitation
                elif contract.contract_request_type and contract.contract_request_type.exploitation:
                    exploitation = contract.contract_request_type.exploitation
            title = 'COMPROMÍS DE PAGAMENT'
        
        company = exploitation.company
        
        ident = payment.due_date.strftime("%d%m%y")
        if limit_date:
            ident = limit_date.strftime("%d%m%y")
        barcode_data = {
            'reference': payment.token if len(payment.token) == 11 else payment.token[:-2],
            'total_final': payment.amount,
            'company': company,
            'ident': ident,
        }
        barcode = generate_barcode(barcode_data)
        if barcode:
            barcode_base64 = base64.b64encode(barcode.getvalue()).decode('utf-8')
        
        iban = payment.payment_bank if payment.payment_bank else None
        if iban:
            hiden_iban = hide_iban(iban)
        
        from billing.utils.barcode_service import get_barcode_values
        barcode_values = get_barcode_values(barcode_data)
        
        file_template = 'payment_doc_template.html'

        main_color = "#074df0"
        secondary_color = "#ffffff"
        try:
            main_color = ConfigProject.objects.get(token='invoice_main_color').value
            secondary_color = ConfigProject.objects.get(token='invoice_secondary_color').value
        except:
            pass
        
        
        company_data = CompanySerializer(exploitation.company, context={'request': request}).data
        
        # Per al PDF, el millor és usar el path absolut local del disc si existeix (xhtml2pdf ho agraeix)
        logo = None
        if exploitation.company.logo:
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
        
        # Imatge d'explotació: si hi ha DOMAIN_MEDIA configurat s'usa la URL absoluta; si no
        # (p.ex. entorn local), cal el path absolut del disc perquè xhtml2pdf la pugui carregar.
        # Un path relatiu com "/media/uploads/..." no es resol i la imatge no apareix al PDF.
        exploitation_image = exploitation_logo_source(exploitation)
        
        clean_sender = str(int(re.sub(r'[^0-9]', '', company_data['vat'] or ''))).zfill(8)
        
        payment_type_token = payment.payment_type_token
        
        selected_company_bank = None
        if payment_type_token == 'BANK_TRANSFER' and payment.payment_bank:
            selected_company_bank = exploitation.company.company_banks.filter(iban=payment.payment_bank, is_active=True).first()

        if not selected_company_bank:
            if invoice and getattr(invoice, 'payment_company_bank', None):
                selected_company_bank = invoice.payment_company_bank
            elif commitment_deposit:
                first_inv = commitment_deposit.invoices.first() if commitment_deposit.invoices.exists() else None
                if first_inv and getattr(first_inv, 'payment_company_bank', None):
                    selected_company_bank = first_inv.payment_company_bank
                elif commitment_deposit.contract and getattr(commitment_deposit.contract, 'payment', None) and getattr(commitment_deposit.contract.payment, 'company_iban', None):
                    selected_company_bank = commitment_deposit.contract.payment.company_iban

        company_bank = selected_company_bank
        if not company_bank:
            company_bank = exploitation.company.company_banks.filter(is_default=True, is_active=True).first()
        if not company_bank:
            company_bank = exploitation.company.company_banks.filter(is_active=True).first()
        
        company_iban = company_bank.iban if company_bank else None
        company_swift = company_bank.swift if company_bank else None
        client_iban = payment.payment_bank
        
        from service.serializers.company_bank_serializer import CompanyBankSerializer
        company_bank_data = CompanyBankSerializer(company_bank).data if company_bank else None

        # Despeses de devolució per impagament: només s'apliquen quan el pagament consta
        # retornat. El ConfigProject només indica l'identificador (token) de la PriceRate a
        # utilitzar; per defecte és null i, en aquest cas, no es mostra la dada a la plantilla.
        # Mateix criteri que a claimrequest/tasks.py (gestió d'impagats).
        return_fee_amount = None
        try:
            returned_status_token = ConfigProject.objects.filter(token='payment_status_returned_token').first()
            is_returned = bool(
                returned_status_token
                and payment.status
                and payment.status.token == returned_status_token.value
            )
            if is_returned:
                from pricing.models import PriceRate
                return_fee_config = ConfigProject.objects.filter(token='claim_letter_return_fee_price_rate_token').first()
                price_rate_token = return_fee_config.value if return_fee_config else None
                if price_rate_token:
                    price_rate = PriceRate.objects.filter(token=price_rate_token, is_active=True).first()
                    billing_range = price_rate.billing_range_active if price_rate else None
                    line_item = billing_range.line_item_types.filter(is_active=True).order_by('id').first() if billing_range else None
                    if line_item and line_item.price is not None:
                        return_fee_amount = line_item.price
        except Exception:
            return_fee_amount = None

        context = {
            'invoice': payment_object,
            'object': payment_object,
            'company': company_data,
            'company_bank': company_bank_data,
            'contract': contract,
            'iban': hiden_iban,
            'barcode': barcode_base64,
            'title': title,
            'total': total,
            'barcode_values': barcode_values,
            'payment_amount': total,
            'due_date': payment.due_date,
            'now_date': payment.due_date,
            'payment_date': payment.payment_date,
            'main_color': main_color,
            'secondary_color': secondary_color,
            'logo': logo,
            'exploitation_image': exploitation_image,
            'sender': clean_sender,
            'reference': payment.token if len(payment.token) == 11 else payment.token[:-2],
            'ident': ident,
            'payment_type_token': payment_type_token,
            'company_iban': company_iban,
            'company_swift': company_swift,
            'client_iban': client_iban,
            'return_fee_amount': return_fee_amount,
            'is_returned': is_returned,
        }
        
        html_rendered = render_to_string(file_template, context)
            
        pdf_buffer = BytesIO()

        # Generate PDF from HTML
        pisa_status = pisa.CreatePDF(html_rendered, dest=pdf_buffer)
        if pisa_status.err:
            raise Exception("PDF generation failed")
            
        #SIGNATURE
        signed_pdf_buffer = sign_pdf(
            pdf_buffer, 
            company, 
            title, 
            'FACTURA'
            )

        # Save PDF to `invoice_file` field in Invoice instance
        pdf_filename = f"{payment.token}.pdf"
        payment._skip_signal = True
        
        service = settings.DOCUMENT_MANAGER_SERVICES.get("billing")
        document_file = upload_document(ContentFile(signed_pdf_buffer.getvalue(), name=pdf_filename), 'PAGAMENT_BANCARI', 'FACTURA', payment.id, payment.token, '', service, pdf_filename)
        
        return document_file, signed_pdf_buffer
    except Exception as e:
        raise Exception(f"Error generating report: {str(e)}")