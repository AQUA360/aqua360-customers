import base64
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
import os
import traceback
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template import Template, Context 
from io import BytesIO

from xhtml2pdf import pisa
from django.core.files.base import ContentFile
from decouple import config

from billing.models import Invoice, InvoiceTemplate
from billing.signals import check_paid_invoice, create_payment_invoice
from billing.utils.barcode_service import generate_barcode, get_barcode_values
from billing.utils.invoice_service import get_totals
from billing.utils.pdf_overlap import client_info_overlaps_header
from billing.utils.message_service import invoice_add_messages
from contract.models import Contract, ContractRequest, ContractTerminationRequest
from faker import Faker
from django.db.models.signals import post_save
from django.conf import settings
from coredata.models import ConfigProject
from coredata.serializers import AddressSerializer
from coredata.utils.address_utils import get_address_complete_without_city
from coredata.utils.pdf_utils import add_watermark_to_pdf
from coredata.utils.template_utils import resolve_template_path
from documentmanager.utils.sign_certificate_service import sign_pdf

from documentmanager.utils.main_utils import upload_document
from service.models import Company, Exploitation
from service.serializers.company_serializer import CompanySerializer
from verifactu.utils.qr_service import generate_qr_base64
fake = Faker()


def invoice_current_file_used_in_communication(invoice):
    """True if the CURRENT invoice PDF Document is attached to an active communication."""
    from communication.models import CommunicationFile

    if not invoice.invoice_file_id:
        return False
    return CommunicationFile.objects.filter(
        file_id=invoice.invoice_file_id,
        is_active=True,
    ).exists()


def invoice_has_communication_retained_pdfs(invoice):
    """True if any Document of this invoice is still linked to a communication."""
    from communication.models import CommunicationFile
    from documentmanager.models import Document

    return CommunicationFile.objects.filter(
        is_active=True,
        file_id__in=Document.objects.filter(
            entity='FACTURES',
            field='FACTURA',
            entity_id=invoice.id,
        ).values_list('id', flat=True),
    ).exists()


def discard_unused_invoice_pdf_document(old_document):
    """
    Remove a previous invoice Document (and its storage file) when it is not
    linked to any active communication. Call only after the invoice points to
    the new Document, because Invoice.invoice_file uses on_delete=CASCADE.
    """
    from communication.models import CommunicationFile
    from documentmanager.utils.main_utils import delete_document

    if not old_document:
        return
    if CommunicationFile.objects.filter(file_id=old_document.id, is_active=True).exists():
        return

    delete_document(old_document)
    old_document.delete()


def prepare_invoice_pdf_filename(invoice):
    """
    Build the PDF filename and optionally remove the previous media file.

    Only the current PDF is kept when THAT document is linked to a communication.
    Intermediate regenerations not used in any communication are deleted.
    A unique filename is used when retained communication PDFs may still exist on disk,
    so their original name is not overwritten.
    """
    keep_previous = invoice_current_file_used_in_communication(invoice)
    if invoice.invoice_file_template and not keep_previous:
        invoice.invoice_file_template.delete()

    base = f"{invoice.serie_final.replace('/', '')}_{invoice.id}"
    if keep_previous or invoice_has_communication_retained_pdfs(invoice):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{base}_{timestamp}.pdf"
    return f"{base}.pdf"


def update_invoice_data(invoice):
    if invoice.connection_request:
        invoice.customer_final = str(invoice.connection_request.person)
        invoice.customer_token_final = invoice.connection_request.person.token
        invoice.address_final = get_address_complete_without_city(invoice.connection_request.address_billing.address) if invoice.connection_request and invoice.connection_request.address_billing else None
        invoice.location_final = invoice.connection_request.address_billing.address.postal_code + ' ' + invoice.connection_request.address_billing.address.city.name if invoice.connection_request and invoice.connection_request.address_billing else None
        invoice.save()
    return invoice

def get_contract_variables(contract):
    """
    Retorna les variables vigents d'un contracte indexades pel token del seu tipus.

    Serveix perquè les plantilles puguin imprimir el valor d'una variable concreta
    (p. ex. el percentatge de {{ contract_variables|get_item:"RENDA-PERSONAL" }})
    sense haver de recórrer la relació a mà. Es fa servir el mateix criteri de
    vigència que generate_variables() de adjustment_service: la variable ha de
    ser activa i la data d'avui ha de caure dins del seu rang.
    """
    variables = {}
    if not contract or not hasattr(contract, 'variables'):
        return variables

    today = datetime.now().date()
    # Prefer .all() so a Prefetch on contract.variables is reused (filter() would re-query).
    for variable in contract.variables.all():
        if not variable.is_active:
            continue
        var_type = variable.type
        if not var_type or not var_type.token:
            continue
        if variable.start_at and today < variable.start_at:
            continue
        if variable.end_at and today > variable.end_at:
            continue
        variables[var_type.token] = variable.value

    return variables


def get_publications_from_lines(lines):
    """
    Processa les línies d'una factura per extreure i agrupar les publicacions associades.
    
    Aquesta funció recorre totes les línies d'una factura i identifica les publicacions
    que estan associades a través del billing_range de cada line_item_type. Per cada
    publicació única trobada, assigna un índex numèric (suffix_index) que s'utilitza
    per mostrar les publicacions a la factura amb un format numerat (ex: "(1) Nom de la publicació").
    Això permet mostrar les publicacions amb identificadors numèrics consecutius en lloc
    d'utilitzar els IDs interns de la base de dades.
    
    Args:
        lines: QuerySet o llista de línies de factura (InvoiceLineItem) a processar
    
    Returns:
        tuple: Una tupla amb dos diccionaris:
            - publications_by_product (dict): Diccionari que agrupa els suffix_index de les
              publicacions per cada product_id. Les claus són product_id i els valors són
              llistes de suffix_index (números consecutius començant per 1).
              Exemple: {1: [1], 2: [2], 3: [1, 3], 4: []}
            - publications_used (dict): Diccionari on les claus són suffix_index (números
              consecutius) i els valors són el nom de la publicació amb el prefix numèric.
              Exemple: {1: "(1) Boletín Oficial", 2: "(2) Diario Oficial", 3: "(3) Gaceta Oficial"}
    """
    # Diccionari per agrupar suffix_index de publicacions per cada product_id
    # Format: {product_id: [suffix_index1, suffix_index2, ...]}
    publications_by_product = {}
    
    # Diccionari per guardar el nom de cada publicació utilitzada amb el seu suffix_index
    # Format: {suffix_index: "(suffix_index) publication_name"}
    publications_used = {}
    
    # Diccionari auxiliar per fer seguiment de quins publication_id ja hem processat
    # i quin suffix_index tenen assignat. Format: {publication_id: suffix_index}
    publication_id_to_suffix = {}
    
    # Inicialitzem el contador de suffix_index fora del bucle perquè s'incrementi correctament
    suffix_index = 0
    
    # Recorrem totes les línies de la factura
    for line in lines:
        # Si la línia no té line_item_type, la saltem
        if not line.line_item_type:
            continue
        
        # Comprovem si la línia té una publicació associada a través del billing_range
        if line.line_item_type.billing_range and line.line_item_type.billing_range.publication:
            # Extreiem les dades de la publicació
            publication_id = line.line_item_type.billing_range.publication.id
            publication_name = line.line_item_type.billing_range.publication.name
            product_id = line.product_id
            
            # Si és la primera vegada que trobem aquesta publicació, li assignem un suffix_index
            # i guardem el nom amb el format numerat per mostrar-lo a la factura
            if publication_id not in publication_id_to_suffix:
                suffix_index += 1
                publication_id_to_suffix[publication_id] = suffix_index
                publications_used[suffix_index] = f"({suffix_index}) {publication_name}"
            
            # Obtenim el suffix_index assignat a aquesta publicació
            current_suffix_index = publication_id_to_suffix[publication_id]
            
            # Afegim el suffix_index a la llista de publicacions associades a aquest producte
            # Això permet saber quines publicacions (identificades pel seu índex numèric) 
            # estan associades a cada producte
            if product_id not in publications_by_product:
                publications_by_product[product_id] = []
            
            # Només afegim el suffix_index si no està ja a la llista per evitar duplicats
            if current_suffix_index not in publications_by_product[product_id]:
                publications_by_product[product_id].append(current_suffix_index)
            
            
    
    # Retornem els dos diccionaris com a tupla
    return publications_by_product, publications_used


def generate(context, invoice, exploitation, temporary=False):
    try:
        messages = invoice_add_messages(invoice)
        # Use exploitation parameter if available, otherwise fall back to invoice.exploitation
        exploitation_obj = exploitation if exploitation else (invoice.exploitation if invoice.exploitation else None)
        if not exploitation_obj:
            default_company = Company.objects.filter(is_default=True, is_active=True).first() or Company.objects.filter(is_active=True).first()
            if default_company:
                exploitation_obj = Exploitation.objects.filter(company=default_company, is_active=True).first() or Exploitation.objects.filter(is_active=True).first()
            else:
                exploitation_obj = Exploitation.objects.filter(is_active=True).first()
            
        if not exploitation_obj:
            raise ValueError("No s'ha trobat l'explotacio de la factura. No es pot generar el PDF.")
            
        if not exploitation_obj.company:
            default_company = Company.objects.filter(is_default=True, is_active=True).first() or Company.objects.filter(is_active=True).first()
            if default_company:
                exploitation_obj.company = default_company
            else:
                raise ValueError("L'explotacio no te cap companyia associada. Revisa la configuracio de la factura.")

        company_obj = invoice.company if invoice.company else exploitation_obj.company
        if not company_obj:
            company_obj = Company.objects.filter(is_default=True, is_active=True).first() or Company.objects.filter(is_active=True).first()

        company = CompanySerializer(company_obj, context=context).data
        if not company or not isinstance(company, dict):
            raise ValueError("No s'han pogut obtenir les dades de la companyia per generar el PDF.")
        barcode = None
        barcode_base64 = None
        barcode_values = None
        
        logo = company_obj.logo.path if company_obj and company_obj.logo else None
        qr_web = None
        if company_obj:
            qr_name = 'qr_web.png'
            qr_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'logo', str(company_obj.id), qr_name)
            if os.path.exists(qr_path):
                if hasattr(settings, 'DOMAIN_MEDIA') and settings.DOMAIN_MEDIA:
                    qr_web = f"{settings.DOMAIN_MEDIA.rstrip('/')}/media/uploads/logo/{company_obj.id}/{qr_name}"
                else:
                    qr_web = qr_path

        
        contract = None
        hiden_iban = None
        is_connection_request = False
        
        try:
            has_printed_template = ConfigProject.objects.get(token='has_preprinted_template').value == 'true'
        except:
            has_printed_template = False

        try:
            show_zero_percent_tax = ConfigProject.objects.get(token='SHOW_ZERO_PERCENT_TAX').value == 'true'
        except:
            show_zero_percent_tax = False

        subtotal, taxes, taxes_base, total = get_totals(invoice, include_zero_percent=show_zero_percent_tax)
        final_taxes = {
            tax_rate: {"tax_value": taxes[tax_rate], "tax_base": taxes_base[tax_rate]}
            for tax_rate in taxes
        }
        
        if invoice.connection_request:
            contract = invoice.connection_request
            is_connection_request = True
        elif invoice.contract:
            contract = Contract.objects.get(id=invoice.contract.id)
        elif invoice.contract_request:
            contract = ContractRequest.objects.get(id=invoice.contract_request.id)
        elif invoice.contract_termination:
            contract = invoice.contract_termination.contract
            
        is_digital = (contract and getattr(contract, 'communication_type', 'DIGITAL') == 'DIGITAL')
        hide_background_and_logos = has_printed_template and not is_digital
        
        try:
            tertiary_color = ConfigProject.objects.get(token='tertiary_color').value
        except:
            tertiary_color = '#d0ecfc'
        
        if invoice.type_final == 'P':
            invoice = update_invoice_data(invoice)
        
        meter_change_readings = []
        try:
            readings_ids = [r.id for r in invoice.readings.all()]
            for reading in invoice.readings.all():
                # Calculem dies si falten per a la lectura actual
                if not reading.consumption_days and reading.previous_reading:
                    reading.consumption_days = (reading.reading_date - reading.previous_reading.reading_date).days

                if reading.previous_reading and reading.previous_reading.is_close:
                    prev = reading.previous_reading
                    # Només l'afegim si NO està ja a les lectures de la factura
                    if prev.id not in readings_ids:
                        # Calculem dies si falten per a la lectura de canvi de comptador
                        if not prev.consumption_days and prev.previous_reading:
                            prev.consumption_days = (prev.reading_date - prev.previous_reading.reading_date).days
                        meter_change_readings.append(prev)

                if reading.previous_reading and reading.previous_reading.previous_reading and reading.previous_reading.previous_reading.is_close:
                    prev_prev = reading.previous_reading.previous_reading
                    # Només l'afegim si NO està ja a les lectures de la factura
                    if prev_prev.id not in readings_ids:
                        # Calculem dies si falten per a la lectura de canvi de comptador (segon nivell)
                        if not prev_prev.consumption_days and prev_prev.previous_reading:
                            prev_prev.consumption_days = (prev_prev.reading_date - prev_prev.previous_reading.reading_date).days
                        meter_change_readings.append(prev_prev)
        except Exception as e:
            print(f"Error en obtenir les lectures de canvi de metre: {str(e)}")
            meter_change_readings = []

        exploitation_image = None
        exploitation_image_path = exploitation_obj.logo.path if exploitation_obj and exploitation_obj.logo else None
        '''
        if os.path.exists(exploitation_image_path):
            try:
                with open(exploitation_image_path, 'rb') as img_file:
                    exploitation_image_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                    exploitation_image = f"data:image/jpeg;base64,{exploitation_image_base64}"
            except Exception as e:
                print(f"Error loading exploitation image: {str(e)}")
                exploitation_image = None
        '''
        
        company_id = company_obj.id if company_obj else None
        domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else settings.MEDIA_ROOT
        ov_image = f"{domain_media}/media/uploads/logo/{company_id}/ov.png" if company_id else None
        
        
        exploitation_image = exploitation_image_path
        now_date = datetime.now().date()
        tomorrow = now_date + timedelta(days=2)
        # Adjust if falls on weekend
        while tomorrow.weekday() >= 5:  
            tomorrow += timedelta(days=1)
        if invoice.payment_type_token_final != 'DIRECT_DEBIT' and invoice.payment_type_token_final != 'BANK_TRANSFER':
            ident = invoice.due_date.strftime("%d%m%y") if invoice.due_date else "000000"
            #ident = tomorrow.strftime("%d%m%y")
            barcode_data = {
                'reference': invoice.token,
                'total_final': invoice.left_to_pay,
                'company': company_obj if company_obj else None,
                'ident': ident,
            }
            barcode = generate_barcode(barcode_data)
            barcode_values = get_barcode_values(barcode_data)
            if barcode:
                barcode_base64 = base64.b64encode(barcode.getvalue()).decode('utf-8')

        verifactu_qr_base64 = None
        if invoice.verifactu_notification:
            verifactu_qr_base64 = f"data:image/png;base64,{generate_qr_base64(invoice.verifactu_notification.verifactu_qr)}"
        
        iban = invoice.payment_bank_final if invoice.payment_bank_final else None
        if iban:
            hiden_iban = hide_iban(iban)
            
        lines = invoice.line_items.filter(is_active=True)
        if not invoice.readings.exists():
            lines = lines.order_by('custom_order', 'id')
            for line in lines:
                if line.custom_order:
                    line.product_order = line.custom_order
                else:
                    line.product_order = line.product.order_priority if line.product and line.product.order_priority else ""
        publications_by_product, publications_used = get_publications_from_lines(lines)

        html_template = None

        physical_address = None
        physical_location = None
        physical_person = None

        invoice_template = InvoiceTemplate.objects.filter(origin=invoice.origin).first()
        is_billing_address = False
        
        att_to = None
        
        if contract:
            if not is_connection_request and contract.address_contact:
                att_to = contract.address_contact.attention_to
                physical_address = get_address_complete_without_city(contract.address_contact.address) if contract.address_contact and contract.address_contact.address else None
                physical_location = contract.address_contact.address.postal_code + ' ' + contract.address_contact.address.city.name if contract.address_contact and contract.address_contact.address else None
                physical_person = str(contract.address_contact.person) if contract.address_contact and contract.address_contact.person else None
            if not is_connection_request:
                supply_address = AddressSerializer(contract.supply_point_default.address).data if contract.supply_point_default and contract.supply_point_default.address else None
            else:
                supply_address = AddressSerializer(contract.address_billing.address).data if contract.address_billing and contract.address_billing.address else None
                is_billing_address = True
        else:
            supply_address = None
        file_template = invoice_template.file_template if invoice_template else None
        
        connection_address = ""
        
        if is_connection_request:
            connection_address = f"{str(contract.address_street)}, {str(contract.address_street_number)}"
        
        if not physical_address and invoice.address_final:
            physical_address = invoice.address_final
            physical_location = invoice.location_final
        if not is_connection_request and not physical_address and contract.supply_point_default and contract.supply_point_default.address:
            physical_address = get_address_complete_without_city(contract.supply_point_default.address)
            physical_location = contract.supply_point_default.address.postal_code + ' ' + contract.supply_point_default.address.city.name if contract.supply_point_default and contract.supply_point_default.address else None
        
        if not physical_person:
            physical_person = invoice.customer_final
        
        allow_watermark = True
        
        if file_template and file_template.file and file_template.file.name.endswith('.html'):
            file_path = file_template.location
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    html_template = f.read()
            except Exception as e:
                print(f"Error en llegir el fitxer: {str(e)}")
        if not html_template:
            invoice_lang = getattr(contract, 'language', None) if contract else None
            if not invoice_lang:
                invoice_lang = settings.LANGUAGE_CODE
            if invoice.readings.exists():
                file_name = resolve_template_path('billing/templates/invoice_template.html', lang=invoice_lang)
            else:
                allow_watermark = False
                file_name = resolve_template_path('billing/templates/invoice_request_template.html', lang=invoice_lang)
            with open(file_name, 'r', encoding='utf-8') as f:
                html_template = f.read()
        django_template = Template(html_template)
        try:
            consumption_day = f"{invoice.consumption / invoice.consumption_days:.2f}"
        except Exception as e:
            consumption_day = f"{0}"
        
        
        used_import = invoice.total_final - invoice.left_to_pay
        try:
            if invoice.left_to_pay != invoice.total_final and contract:
                piggy_bank = contract.piggy_bank
                if piggy_bank:
                    last_movement = piggy_bank.movements.order_by('-created_at').filter(payment__in=invoice.payments.all()).first()
                    if last_movement and not last_movement.is_positive:
                        used_import = last_movement.amount
        except:
            pass
        
        corrected_readings = []
        for reading in invoice.readings.all():
            if reading.estimated_used and reading.estimated_used > 0:
                corrected_readings.append(reading)

        other_pending_invoices_count = 0
        other_pending_invoices_total = 0.00
        if invoice.contract:
            budget_token = None
            try:
                budget_token = ConfigProject.objects.get(token='invoice_type_budget_token').value
            except:
                pass

            pending_status_tokens = ['2', '3', '-1', '-3', '4']
            try:
                tokens_to_fetch = [
                    'invoice_status_confirmed_token',
                    'invoice_status_sent_token',
                    'invoice_status_expired_token',
                    'invoice_status_endowment_token',
                    'invoice_status_commitment_token'
                ]
                fetched_values = list(ConfigProject.objects.filter(token__in=tokens_to_fetch).values_list('value', flat=True))
                if fetched_values:
                    pending_status_tokens = fetched_values
            except:
                pass

            pending_query = Invoice.objects.filter(
                contract=invoice.contract,
                is_active=True,
                is_confirmed=True,
                left_to_pay__gt=0,
                status__token__in=pending_status_tokens
            ).exclude(id=invoice.id)
            if budget_token:
                pending_query = pending_query.exclude(type_final=budget_token)
            
            other_pending_invoices_count = pending_query.count()
            from django.db.models import Sum
            total_sum = pending_query.aggregate(Sum('left_to_pay'))['left_to_pay__sum']
            if total_sum:
                other_pending_invoices_total = float(total_sum)


        main_color = "#074df0"
        secondary_color = "#ffffff"
        try:
            main_color = company_obj.invoice_main_color if company_obj.invoice_main_color else ConfigProject.objects.get(token='invoice_main_color').value
            secondary_color = company_obj.invoice_secondary_color if company_obj.invoice_secondary_color else ConfigProject.objects.get(token='invoice_secondary_color').value
        except:
            pass
        
        
        is_invoice = True
        try:
            invoice_type_budget_token = ConfigProject.objects.get(token='invoice_type_budget_token').value
            if invoice_type_budget_token == invoice.type_final:
                is_invoice = False
        except:
            pass
        
        billing_period = None
        try:
            if invoice.billing:
                period_type = ['mensual','bimestral','trimestral','semestral','anual']
                period_jumps = [1,2,3,6,12]
                reading = invoice.readings.first()
                if reading:
                    current_date = reading.reading_date
                period = invoice.billing.biller.period_type
                if period:
                    period_index = period_type.index(period)
                    period_jump = period_jumps[period_index]
                    post_date = current_date - relativedelta(months=period_jump)
                billing_period = f"{post_date.strftime('%d/%m/%Y')} - {current_date.strftime('%d/%m/%Y')}"
        except Exception as e:
            print(e)
            pass
        
        show_meter = True
        try:
            meter_status_token = ConfigProject.objects.get(token='token_meter_status_no_meter').value
            if contract and contract.supply_point_default and contract.supply_point_default.meter and contract.supply_point_default.meter.status.token == meter_status_token:
                show_meter = False
        except:
            pass

        company_bank = None
        if getattr(invoice, 'payment_company_bank', None):
            from service.serializers.company_bank_serializer import CompanyBankSerializer
            company_bank = CompanyBankSerializer(invoice.payment_company_bank).data
        elif company and company.get("company_banks"):
            for cb in company.get("company_banks"):
                if cb.get("is_default") and cb.get("is_active"):
                    company_bank = cb
                    break
            if not company_bank:
                for cb in company.get("company_banks"):
                    if cb.get("is_active"):
                        company_bank = cb
                        break
            if not company_bank:
                company_bank = company.get("company_banks")[0]

        print(f"[utils/invoice_pdf.py] logo: {logo}")
        print(f"[utils/invoice_pdf.py] exploitation_image: {exploitation_image}")

        context = Context({
            'invoice': invoice,
            'company': company,
            'company_bank': company_bank,
            'logo': logo,
            'exploitation_image': exploitation_image,
            'contract': contract,
            'iban': hiden_iban,
            'taxes': final_taxes,
            'messages': messages,
            'lines': lines,
            'consumption_day': consumption_day,
            'barcode': barcode_base64,
            'barcode_values': barcode_values,
            'used_import': used_import,
            'corrected_readings': corrected_readings,
            'other_pending_invoices_count': other_pending_invoices_count,
            'other_pending_invoices_total': other_pending_invoices_total,
            'main_color': main_color,
            'secondary_color': secondary_color,
            'is_invoice': is_invoice,
            'billing_period': billing_period,
            'supply_address': supply_address,
            'is_billing_address': is_billing_address,
            'is_connection_request': is_connection_request,
            'is_digital': is_digital,
            'hide_background_and_logos': hide_background_and_logos,
            'tertiary_color': tertiary_color if is_digital else None,
            'show_meter': show_meter,
            'verifactu_qr': verifactu_qr_base64,
            'qr_web': qr_web,
            'meter_change_readings': meter_change_readings,
            'ov_image': ov_image,
            'physical_address': physical_address,
            'physical_location': physical_location,
            'physical_person': physical_person,
            'contract_variables': get_contract_variables(contract),
            'publications_by_product': publications_by_product,
            'publications_used': publications_used,
            'att_to': att_to,
            'connection_address': connection_address,
            'footer_text': company_obj.invoice_footer_text if company_obj and company_obj.invoice_footer_text else None,
            'data_protection_law_text': company_obj.data_protection_law_text if company_obj and company_obj.data_protection_law_text else None,
            'force_client_info_next_page': False
        })
        html_rendered = django_template.render(context)

        pdf_buffer = BytesIO()

        # PDF from HTML
        pisa_status = pisa.CreatePDF(html_rendered, dest=pdf_buffer)
        if pisa_status.err:
            error_msg = f"Error PISA en generar el PDF: {str(pisa_status.err)}"
            print(error_msg)
            raise Exception(error_msg)

        # xhtml2pdf no crea una nova pàgina quan el contingut desborda el
        # content_frame: el text sobrant es torna a dibuixar des de dalt de
        # la mateixa pàgina, sobreposant-se al que ja hi havia. Detectem
        # aquest solapament i, només llavors, forcem un salt de pàgina
        # explícit abans del bloc "INFORMACIÓ AL CLIENT" i tornem a renderitzar.
        if client_info_overlaps_header(pdf_buffer):
            context['force_client_info_next_page'] = True
            html_rendered = django_template.render(context)
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html_rendered, dest=pdf_buffer)
            if pisa_status.err:
                error_msg = f"Error PISA en generar el PDF: {str(pisa_status.err)}"
                print(error_msg)
                raise Exception(error_msg)

        pdf_filename = prepare_invoice_pdf_filename(invoice)
        
        #post_save.disconnect(create_payment_invoice, Invoice)
        post_save.disconnect(check_paid_invoice, Invoice)
        
        try:
            bg_img = os.path.join("config", "assets", "bg_img.png")
            pdf_buffer = add_watermark_to_pdf(pdf_buffer, bg_img, True)
        except Exception as e:
            print(f"Error en afegir el fons: {str(e)}")
        
        test_watermark_path = None
        
        if config('ENV', default='-').upper() == 'TEST' or config('ENV', default='-').upper() == 'LOCAL':
            try:
                test_watermark_path = os.path.join("config", "assets", "test-watermark.png")
            except Exception as e:
                print(f"Error en afegir el fons: {str(e)}")
        
        
        
        old_document = None
        if temporary and allow_watermark:
            # Apply watermark
            watermark_path = os.path.join("config", "assets", "watermark.png")  # Path to watermark
            try:
                if test_watermark_path:
                    watermarked_pdf_buffer = add_watermark_to_pdf(pdf_buffer, test_watermark_path, opacity=0.1)
                else:
                    watermarked_pdf_buffer = add_watermark_to_pdf(pdf_buffer, watermark_path)
                # Save the new watermarked PDF
                invoice.invoice_file_template.save(pdf_filename, ContentFile(watermarked_pdf_buffer.getvalue()))
            except Exception as e:
                error_msg = f"Error en afegir watermark o guardar PDF temporal: {str(e)}"
                print(error_msg)
                raise Exception(error_msg)
        else:
            if test_watermark_path:
                pdf_buffer = add_watermark_to_pdf(pdf_buffer, test_watermark_path)
            try:
                invoice.invoice_file_template.save(pdf_filename, ContentFile(pdf_buffer.getvalue()))
            except Exception as e:
                error_msg = f"Error en guardar PDF: {str(e)}"
                print(error_msg)
                raise Exception(error_msg)
            
            signed_pdf_buffer = sign_pdf(
                pdf_buffer, 
                company, 
                invoice.title_final if invoice.title_final else '', 
                'FACTURA'
                )
                    
            service = settings.DOCUMENT_MANAGER_SERVICES.get("billing")
            old_document = invoice.invoice_file
            document_file = upload_document(ContentFile(signed_pdf_buffer.getvalue()), 'FACTURES', 'FACTURA', invoice.id, invoice.customer_token_final, '', service, pdf_filename)
            invoice.invoice_file = document_file
        invoice._skip_pdf_generation = True
        invoice.save()
        discard_unused_invoice_pdf_document(old_document)
        
        #post_save.connect(create_payment_invoice, Invoice)
        post_save.connect(check_paid_invoice, Invoice)
            
    except Exception as e:
        error_msg = f"Error en generar el PDF: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        raise Exception(error_msg)

def hide_iban(iban):
    iban = iban.replace(" ", "") 

    if len(iban) < 8:  
        return iban 

    country_code = iban[:4]
    last_digits = iban[-4:]
    middle_length = len(iban) - 8
    middle_masked = "*" * middle_length

    return country_code + middle_masked + last_digits
    # other way to hide iban
    country_code = iban[:-6]
    last_masked = "*" * 6
    

    return country_code +  last_masked