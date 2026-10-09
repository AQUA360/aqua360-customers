from datetime import timedelta, datetime
from decouple import config
from django.conf import settings
from dateutil.relativedelta import relativedelta
import os
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import FileResponse, JsonResponse
from django.core.files.base import ContentFile
from django.db.models import Count, Prefetch, Sum
from rest_framework.views import APIView, Response
from io import BytesIO
from xhtml2pdf import pisa
from django.template import Template, Context 
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.utils.invoice_service import get_totals
from billing.utils.message_service import invoice_add_messages
from billing.utils.pdf_overlap import client_info_overlaps_header
from contract.models import Contract, ContractRequest, Variable
from coredata.models import City
from coredata.serializers import AddressSerializer, PersonCardSerializer
from coredata.utils.address_utils import get_address_complete_without_city
from coredata.utils.template_utils import build_template_candidates
from coredata.utils.pdf_utils import add_watermark_to_pdf
from documentmanager.utils.main_utils import upload_document
from documentmanager.utils.sign_certificate_service import sign_pdf
from service.models import Company, Exploitation
from service.serializers.company_serializer import CompanySerializer
from ..models import Invoice, InvoiceLineItem, InvoiceTemplate, Reading
from service.utils.exploitation_logo import exploitation_logo_path
from coredata.models import ConfigProject
from billing.utils.barcode_service import generate_barcode, get_barcode_values
import base64
from verifactu.utils.qr_service import generate_qr_base64


PDF_CONFIG_TOKENS = (
    'has_preprinted_template',
    'tertiary_color',
    'token_simplified_invoice_serie',
    'SHOW_ZERO_PERCENT_TAX',
    'invoice_type_budget_token',
    'invoice_status_confirmed_token',
    'invoice_status_sent_token',
    'invoice_status_expired_token',
    'invoice_status_endowment_token',
    'invoice_status_commitment_token',
    'invoice_main_color',
    'invoice_secondary_color',
    'token_meter_status_no_meter',
)


class InvoiceReportPDFDownloadViewSet(APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = Invoice.objects.all().order_by('-created_at')
  def get(self, request, id, *args, **kwargs):
    invoice = get_invoice_for_pdf(invoice_id=id)
    context = {'request': request}
    file_url, document_id, _ = generate_report_invoice_pdf(
        invoice, request, context, is_digital=True
    )
        
    return JsonResponse({"pdf_url": file_url, "document_id": document_id})

def resolve_invoice_template_name(base_name, lang):
    for candidate in build_template_candidates(base_name, lang=lang):
        if os.path.exists(os.path.join(settings.BASE_DIR, 'billing', 'templates', candidate)):
            return candidate
    return base_name

def get_config_value(token, default=None, config_cache=None):
    if config_cache is not None and token in config_cache:
        return config_cache[token]
    try:
        val = ConfigProject.objects.get(token=token).value
        if config_cache is not None:
            config_cache[token] = val
        return val
    except ConfigProject.DoesNotExist:
        if config_cache is not None:
            config_cache[token] = default
        return default


def warm_pdf_config_cache(config_cache=None):
    """Load all ConfigProject tokens used by PDF generation in one query."""
    if config_cache is None:
        config_cache = {}
    missing = [token for token in PDF_CONFIG_TOKENS if token not in config_cache]
    if missing:
        for row in ConfigProject.objects.filter(token__in=missing).only('token', 'value'):
            config_cache[row.token] = row.value
        for token in missing:
            config_cache.setdefault(token, None)
    return config_cache


def get_invoice_for_pdf(invoice_id=None, invoice=None):
    """Reload invoice with relations needed for PDF generation."""
    reading_qs = Reading.objects.select_related(
        'previous_reading',
        'previous_reading__previous_reading',
        'previous_reading__previous_reading__previous_reading',
        'meter',
    )
    line_item_qs = InvoiceLineItem.objects.filter(is_active=True).select_related(
        'product',
        'line_item_type',
        'line_item_type__billing_range',
        'line_item_type__billing_range__publication',
    ).order_by('custom_order', 'id')
    variable_qs = Variable.objects.select_related('type')

    qs = Invoice.objects.select_related(
        'status',
        'serie',
        'type',
        'origin',
        'company',
        'exploitation',
        'exploitation__company',
        'billing',
        'billing__biller',
        'verifactu_notification',
        'template',
        'contract',
        'contract__address_contact',
        'contract__address_contact__address',
        'contract__address_contact__address__city',
        'contract__address_contact__person',
        'contract__supply_point_default',
        'contract__supply_point_default__address',
        'contract__supply_point_default__address__city',
        'contract__supply_point_default__meter',
        'contract__supply_point_default__meter__status',
        'contract__piggy_bank',
        'contract_request',
        'contract_request__address_contact',
        'contract_request__address_contact__address',
        'contract_request__address_contact__address__city',
        'contract_request__address_contact__person',
        'contract_request__supply_point_default',
        'contract_request__supply_point_default__address',
        'contract_request__supply_point_default__address__city',
        'contract_request__supply_point_default__meter',
        'contract_request__supply_point_default__meter__status',
        'contract_termination',
        'contract_termination__contract',
        'contract_termination__contract__address_contact',
        'contract_termination__contract__address_contact__address',
        'contract_termination__contract__address_contact__address__city',
        'contract_termination__contract__supply_point_default',
        'contract_termination__contract__supply_point_default__address',
        'contract_termination__contract__supply_point_default__meter',
        'contract_termination__contract__supply_point_default__meter__status',
        'contract_termination__contract__piggy_bank',
        'connection_request',
        'connection_request__connection',
        'connection_request__connection__address_street',
        'connection_request__connection__address_street_number',
        'connection_request__address_street',
        'connection_request__address_street_number',
        'connection_request__address_billing',
        'connection_request__address_billing__address',
        'connection_request__address_billing__address__city',
        'connection_request__person',
    ).prefetch_related(
        Prefetch('readings', queryset=reading_qs),
        Prefetch('line_items', queryset=line_item_qs),
        Prefetch('payments'),
        Prefetch('contract__variables', queryset=variable_qs),
        Prefetch('contract_request__variables', queryset=variable_qs),
        Prefetch('contract_termination__contract__variables', queryset=variable_qs),
        Prefetch('company__company_banks'),
        Prefetch('exploitation__company__company_banks'),
    )

    if invoice is not None:
        return qs.get(pk=invoice.pk)
    return get_object_or_404(qs, id=invoice_id)

def generate_report_invoice_pdf(invoice, request = None, context = None, save_pdf = True, is_digital = False, config_cache = None):
    try:
        # `get_invoice_for_pdf()` retorna una INSTANCIA NOVA (refetch amb els
        # select_related/prefetch_related del PDF), no la que ens ha passat qui crida.
        # Guardem la original per poder-li propagar despres els camps del PDF: si no,
        # el seu objecte es queda amb invoice_file/invoice_file_template buits i el
        # seguent .save() que hi faci esborra el document acabat de generar.
        source_invoice = invoice
        invoice = get_invoice_for_pdf(invoice=invoice)
        config_cache = warm_pdf_config_cache(config_cache)

        has_printed_template = get_config_value('has_preprinted_template', 'false', config_cache) == 'true'
        contract = None
        is_connection_request = False
        connection_address = None
        
        if invoice.connection_request:
            contract = invoice.connection_request
            is_connection_request = True
        elif invoice.contract:
            contract = invoice.contract
        elif invoice.contract_request:
            contract = invoice.contract_request
        elif invoice.contract_termination:
            contract = invoice.contract_termination.contract
            
        is_digital = (contract and getattr(contract, 'communication_type', 'DIGITAL') == 'DIGITAL')
        hide_background_and_logos = has_printed_template and not is_digital
        
        tertiary_color = get_config_value('tertiary_color', '#d0ecfc', config_cache)
        
        messages = invoice_add_messages(invoice, hide_background_and_logos=hide_background_and_logos)
        exploitation = invoice.exploitation
        if not exploitation:
            default_company = Company.objects.filter(is_default=True, is_active=True).first() or Company.objects.filter(is_active=True).first()
            if default_company:
                exploitation = Exploitation.objects.filter(company=default_company, is_active=True).first() or Exploitation.objects.filter(is_active=True).first()
            else:
                exploitation = Exploitation.objects.filter(is_active=True).first()

        company_obj = invoice.company if invoice.company else exploitation.company if exploitation else None
        if not company_obj:
            company_obj = Company.objects.filter(is_default=True, is_active=True).first() or Company.objects.filter(is_active=True).first()
        
        company_main = Company.objects.filter(id=1).first()
        hiden_iban = None
        other_template = False
        
        company_serialized = CompanySerializer(company_obj, context={'request': request}).data if company_obj else None
        logo_db = company_serialized['logo'] if company_serialized else None
        logo = None
        if not logo_db:
            c = Company.objects.all().first()
            company_serialized = CompanySerializer(c, context={'request': request}).data if c else None
            logo_db = company_serialized['logo'] if company_serialized else None
        
        if logo_db:
            # netejem logo_db assegurant-nos que sempre arriba el mateix format, potser que arribi una url o un path que comenci per /media/
            logo_db = f'uploads/{logo_db.split("uploads/")[1]}'
            
            # Logo és un path relatiu, construir path complet
            if hasattr(settings, 'DOMAIN_MEDIA') and settings.DOMAIN_MEDIA:
                logo = os.path.join(settings.DOMAIN_MEDIA, f'media/{logo_db}')
            else:
                logo = os.path.join(settings.MEDIA_ROOT, logo_db)
        
        barcode = None
        barcode_base64 = None
        
        simplified_invoice_token = get_config_value('token_simplified_invoice_serie', '', config_cache)
        
        show_zero_percent_tax = get_config_value('SHOW_ZERO_PERCENT_TAX', 'false', config_cache) == 'true'

        # Cache related collections once (prefetch-backed).
        readings = list(invoice.readings.all())
        has_readings = bool(readings)
        lines = list(invoice.line_items.all())  # already filtered is_active=True in Prefetch
        if not has_readings:
            for line in lines:
                if line.custom_order:
                    line.product_order = line.custom_order
                else:
                    line.product_order = line.product.order_priority if line.product and line.product.order_priority else ""

        subtotal, taxes, taxes_base, total = get_totals(
            invoice,
            include_zero_percent=show_zero_percent_tax,
            line_items=lines,
        )
        
        final_taxes = {
        tax_rate: {"tax_value": taxes[tax_rate], "tax_base": taxes_base[tax_rate]}
        for tax_rate in taxes
        }
        
        if not contract:
            if invoice.connection_request:
                contract = invoice.connection_request
                is_connection_request = True
            elif invoice.contract:
                contract = invoice.contract
            elif invoice.contract_request:
                contract = invoice.contract_request
            elif invoice.contract_termination:
                contract = invoice.contract_termination.contract
        
        if is_connection_request and contract:
            try:
                # ConnectionRequest points to a Connection, which has the address fields
                street = contract.address_street or (contract.connection.address_street if hasattr(contract, 'connection') and contract.connection else None)
                number = contract.address_street_number or (contract.connection.address_street_number if hasattr(contract, 'connection') and contract.connection else None)
                
                street_name = str(street) if street else ""
                number_val = str(number) if number and str(number) != "None" else ""
                
                if street_name:
                    connection_address = f"{street_name}, {number_val}".strip(', ')
            except:
                pass
        exploitation_image = exploitation_logo_path(exploitation) if exploitation and exploitation.id else None

        domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''
        ov_image = os.path.join(settings.MEDIA_ROOT, f"uploads/logo/{company_serialized['id']}/ov.png") if company_serialized else None
        now_date = datetime.now().date()
        tomorrow = now_date + timedelta(days=2)
        # Adjust if falls on weekend
        while tomorrow.weekday() >= 5:  
            tomorrow += timedelta(days=1)
        if invoice.payment_type_token_final != 'DIRECT_DEBIT' and invoice.payment_type_token_final != 'BANK_TRANSFER':
            ident = invoice.due_date.strftime("%d%m%y") if invoice.due_date else "000000"
            if company_obj:
                #ident = tomorrow.strftime("%d%m%y")
                barcode_data = {
                    'reference': invoice.token,
                    'total_final': invoice.left_to_pay,
                    'company': company_obj,
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
        
        consumption_day = None
        if invoice.consumption and invoice.consumption_days:
            consumption_day = f"{invoice.consumption / invoice.consumption_days:.2f}"
        
        
        from billing.utils.invoice_pdf import get_contract_variables, get_publications_from_lines
        publications_by_product, publications_used = get_publications_from_lines(lines)

        invoice_lang = contract.language if contract and getattr(contract, 'language', None) else settings.LANGUAGE_CODE
        try:
            invoice_template = InvoiceTemplate.objects.filter(origin=invoice.origin).first()
            if invoice_template and invoice_template.file_template:
                file_template = invoice_template.file_template
            else:
                base_name = 'invoice_template.html' if has_readings else 'invoice_request_template.html'
                file_template = resolve_invoice_template_name(base_name, invoice_lang)
                other_template = True
        except:
            base_name = 'invoice_template.html' if has_readings else 'invoice_request_template.html'
            file_template = resolve_invoice_template_name(base_name, invoice_lang)
            other_template = True
        
        if invoice.serie and invoice.serie.token == simplified_invoice_token or invoice.simplified:
            file_template = 'simplified_invoice_template.html'
            other_template = True

        total_final = invoice.total_final or 0
        left_to_pay = invoice.left_to_pay or 0
        used_import = total_final - left_to_pay
        try:
            if invoice.left_to_pay != invoice.total_final and contract:
                piggy_bank = getattr(contract, 'piggy_bank', None)
                if piggy_bank:
                    payment_ids = [p.id for p in invoice.payments.all()]
                    last_movement = piggy_bank.movements.order_by('-created_at').filter(payment_id__in=payment_ids).first()
                    if last_movement and not last_movement.is_positive:
                        used_import = last_movement.amount
        except:
            pass
        physical_person = None
        att_to = None
        physical_address = None
        physical_location = None
        supply_address = None
        if contract:
            if is_connection_request:
                physical_address = get_address_complete_without_city(contract.address_billing.address) if contract.address_billing and contract.address_billing.address else None
                physical_location = contract.address_billing.address.postal_code + ' ' + contract.address_billing.address.city.name if contract.address_billing and contract.address_billing.address else None
                physical_person = str(contract.person) if contract.person else None
            else:
                address_contact = getattr(contract, 'address_contact', None)
                if address_contact:
                    physical_address = get_address_complete_without_city(address_contact.address) if address_contact.address else None
                    physical_location = address_contact.address.postal_code + ' ' + address_contact.address.city.name if address_contact.address else None
                    physical_person = str(address_contact.person) if address_contact.person else None
                    att_to = address_contact.attention_to if address_contact.attention_to else None
        supply_point_default = getattr(contract, 'supply_point_default', None)
        if supply_point_default and supply_point_default.address:
            supply_address = AddressSerializer(supply_point_default.address).data

        if not physical_address and invoice.address_final:
            physical_address = invoice.address_final
            physical_location = invoice.location_final
        if not physical_address and supply_point_default and supply_point_default.address:
            physical_address = get_address_complete_without_city(supply_point_default.address)
            physical_location = supply_point_default.address.postal_code + ' ' + supply_point_default.address.city.name if supply_point_default and supply_point_default.address else None
        if not physical_person:
            physical_person = invoice.customer_final

        corrected_readings = [
            reading for reading in readings
            if reading.estimated_used and reading.estimated_used > 0
        ]
        
        other_pending_invoices_count = 0
        other_pending_invoices_total = 0.00
        if invoice.contract:
            budget_token = get_config_value('invoice_type_budget_token', None, config_cache)

            pending_status_tokens = ['2', '3', '-1', '-3', '4']
            try:
                tokens_to_fetch = [
                    'invoice_status_confirmed_token',
                    'invoice_status_sent_token',
                    'invoice_status_expired_token',
                    'invoice_status_endowment_token',
                    'invoice_status_commitment_token'
                ]
                fetched_values = []
                for tok in tokens_to_fetch:
                    val = get_config_value(tok, None, config_cache)
                    if val is not None:
                        fetched_values.append(val)
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
            
            pending_agg = pending_query.aggregate(
                count=Count('id'),
                total=Sum('left_to_pay'),
            )
            other_pending_invoices_count = pending_agg['count'] or 0
            if pending_agg['total']:
                other_pending_invoices_total = float(pending_agg['total'])

        
        main_color = "#074df0"
        secondary_color = "#ffffff"
        try:
            main_color = company_obj.invoice_main_color if company_obj.invoice_main_color else get_config_value('invoice_main_color', '#074df0', config_cache)
            secondary_color = company_obj.invoice_secondary_color if company_obj.invoice_secondary_color else get_config_value('invoice_secondary_color', '#ffffff', config_cache)
        except:
            pass

        background_image = None
        if config('ENV', default='-').upper() == 'TEST' or config('ENV', default='-').upper() == 'LOCAL':
            background_image = os.path.join(settings.BASE_DIR, "config", "assets", "test-watermark-plantilla.png")
            if not os.path.exists(background_image):
                background_image = None
        
        is_invoice = True
        try:
            invoice_type_budget_token = get_config_value('invoice_type_budget_token', None, config_cache)
            if invoice_type_budget_token == invoice.type_final:
                is_invoice = False
        except:
            pass
        
        billing_period = None
        try:
            if invoice.billing:
                period_type = ['mensual','bimestral','trimestral','semestral','anual']
                period_jumps = [1,2,3,6,12]
                reading = readings[0] if readings else None
                if reading:
                    current_date = reading.reading_date
                period = invoice.billing.biller.period_type
                if period:
                    period_index = period_type.index(period)
                    period_jump = period_jumps[period_index]
                    post_date = current_date - relativedelta(months=period_jump)
                billing_period = f"{post_date.strftime('%d/%m/%Y')} - {current_date.strftime('%d/%m/%Y')}"
        except:
            pass
        
        show_meter = True
        try:
            meter_status_token = get_config_value('token_meter_status_no_meter', None, config_cache)
            supply_point_default = getattr(contract, 'supply_point_default', None)
            if supply_point_default and supply_point_default.meter and supply_point_default.meter.status.token == meter_status_token:
                show_meter = False
        except:
            pass
        
        meter_change_readings = []
        try:
            readings_ids = {r.id for r in readings}
            for reading in readings:
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
        company_bank = None
        if company_serialized:
            company_bank = company_serialized.get("company_banks")[0] if company_serialized.get("company_banks") else None

        num_habitatges = None
        if contract and hasattr(contract, 'variables'):
            # Use prefetched variables (.all()), avoid .filter() re-query.
            for variable in contract.variables.all():
                if (
                    variable.is_active
                    and variable.type
                    and variable.type.name == 'General'
                ):
                    num_habitatges = variable.value
                    break

        contract_variables = get_contract_variables(contract)

        if other_template:
            render_context = {
                'invoice': invoice,
                'num_habitatges': num_habitatges,
                'company': company_obj,
                'company_main': company_main,
                'company_bank': company_bank,
                'contract': contract,
                'is_connection_request': is_connection_request,
                'connection_address': connection_address,
                'logo': logo,
                'exploitation_image': exploitation_image,
                'iban': hiden_iban,
                'taxes': final_taxes,
                'messages': messages,
                'lines': lines,
                'consumption_day': consumption_day,
                'barcode': barcode_base64,
                'barcode_values': barcode_values if 'barcode_values' in locals() else None,
                'used_import': used_import,
                'corrected_readings': corrected_readings,
                'other_pending_invoices_count': other_pending_invoices_count,
                'other_pending_invoices_total': other_pending_invoices_total,
                'main_color': main_color,
                'secondary_color': secondary_color,
                'is_invoice': is_invoice,
                'billing_period': billing_period,
                'supply_address': supply_address,
                'show_meter': show_meter,
                'meter_change_readings': meter_change_readings,
                'verifactu_qr': verifactu_qr_base64,
                'ov_image': ov_image,
                'physical_address': physical_address,
                'physical_location': physical_location,
                'physical_person': physical_person,
                'contract_variables': contract_variables,
                'publications_by_product': publications_by_product,
                'publications_used': publications_used,
                'att_to': att_to,
                'footer_text': company_obj.invoice_footer_text if company_obj and company_obj.invoice_footer_text else None,
                'background_image': background_image,
                'hide_background_and_logos': hide_background_and_logos,
                'is_digital': is_digital,
                'tertiary_color': tertiary_color if is_digital else None,
                'data_protection_law_text': company_obj.data_protection_law_text if company_obj and company_obj.data_protection_law_text else None,
                'force_client_info_next_page': False
                }
            html_rendered = render_to_string(file_template, render_context)
        else:
            if file_template and file_template.location and file_template.document_name.endswith('.html'):
                file_path = file_template.location
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        html_template = f.read()
                except Exception as e:
                    raise Exception(f"Failed to read template: {str(e)}")
            else:
                raise Exception('Invalid template file')
            django_template = Template(html_template)

            context = Context({
                'invoice': invoice,
                'num_habitatges': num_habitatges,
                'company': company_obj,
                'company_main': company_main,
                'company_bank': company_bank,
                'contract': contract,
                'is_connection_request': is_connection_request,
                'connection_address': connection_address,
                'logo': logo,
                'exploitation_image': exploitation_image,
                'iban': hiden_iban,
                'taxes': final_taxes,
                'messages': messages,
                'lines': lines,
                'consumption_day': consumption_day,
                'barcode': barcode_base64,
                'barcode_values': barcode_values if 'barcode_values' in locals() else None,
                'used_import': used_import,
                'corrected_readings': corrected_readings,
                'other_pending_invoices_count': other_pending_invoices_count,
                'other_pending_invoices_total': other_pending_invoices_total,
                'main_color': main_color,
                'secondary_color': secondary_color,
                'is_invoice': is_invoice,
                'billing_period': billing_period,
                'supply_address': supply_address,
                'show_meter': show_meter,
                'meter_change_readings': meter_change_readings,
                'verifactu_qr': verifactu_qr_base64,
                'ov_image': ov_image,
                'physical_address': physical_address,
                'physical_location': physical_location,
                'physical_person': physical_person,
                'contract_variables': contract_variables,
                'publications_by_product': publications_by_product,
                'publications_used': publications_used,
                'att_to': att_to,
                'footer_text': company_obj.invoice_footer_text if company_obj and company_obj.invoice_footer_text else None,
                'background_image': background_image,
                'hide_background_and_logos': hide_background_and_logos,
                'data_protection_law_text': company_obj.data_protection_law_text if company_obj and company_obj.data_protection_law_text else None,
                'force_client_info_next_page': False
            })
            html_rendered = django_template.render(context)

        pdf_buffer = BytesIO()

        # Generate PDF from HTML
        pisa_status = pisa.CreatePDF(html_rendered, dest=pdf_buffer)
        if pisa_status.err:
            return JsonResponse({"error": "PDF generation failed"}, status=500)

        # xhtml2pdf no crea una nova pàgina quan el contingut desborda el
        # content_frame: el text sobrant es torna a dibuixar des de dalt de
        # la mateixa pàgina, sobreposant-se al que ja hi havia. Detectem
        # aquest solapament i, només llavors, forcem un salt de pàgina
        # explícit abans del bloc "INFORMACIÓ AL CLIENT" i tornem a renderitzar.
        if client_info_overlaps_header(pdf_buffer):
            if other_template:
                render_context['force_client_info_next_page'] = True
                html_rendered = render_to_string(file_template, render_context)
            else:
                context['force_client_info_next_page'] = True
                html_rendered = django_template.render(context)
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html_rendered, dest=pdf_buffer)
            if pisa_status.err:
                return JsonResponse({"error": "PDF generation failed"}, status=500)
        
        # Add watermark if in test environment (after PDF is generated)
        if config('ENV', default='-').upper() == 'TEST' or config('ENV', default='-').upper() == 'LOCAL':
            try:
                test_watermark_path = os.path.join("config", "assets", "test-watermark.png")
                pdf_buffer = add_watermark_to_pdf(pdf_buffer, test_watermark_path, opacity=0.1)
            except Exception as e:
                print(f"Error en afegir el fons: {str(e)}")
        
        #SIGNATURE
        signed_pdf_buffer = sign_pdf(
            pdf_buffer, 
            company_obj, 
            invoice.title_final if invoice.title_final else '', 
            'FACTURA'
            )

        # Save PDF to `invoice_file` field in Invoice instance.
        # Keep previous media only if THAT document is linked to a communication.
        from billing.utils.invoice_pdf import (
            discard_unused_invoice_pdf_document,
            prepare_invoice_pdf_filename,
        )
        old_document = invoice.invoice_file
        pdf_filename = prepare_invoice_pdf_filename(invoice)
        invoice._skip_signal = True
        invoice.invoice_file_template.save(pdf_filename, ContentFile(signed_pdf_buffer.getvalue()))
        
        service = settings.DOCUMENT_MANAGER_SERVICES.get("billing")
        document_id = None
        if save_pdf:
            document_file = upload_document(ContentFile(signed_pdf_buffer.getvalue()), 'FACTURES', 'FACTURA', invoice.id, invoice.customer_token_final, '', service, pdf_filename)
            invoice.invoice_file = document_file
            invoice._skip_signal = True
            invoice.save()
            document_id = document_file.id
            discard_unused_invoice_pdf_document(old_document)

        # Sincronitzem els camps del PDF amb la instancia de qui ens ha cridat.
        if source_invoice is not None and source_invoice is not invoice:
            source_invoice.invoice_file_template = invoice.invoice_file_template.name
            source_invoice.invoice_file = invoice.invoice_file

        file_url = None
        if request:
            try:
                file_url = request.build_absolute_uri(invoice.invoice_file_template.url)
            except:
                file_url = None
        
        return file_url, document_id, signed_pdf_buffer
    except Exception as e:
        raise Exception(f"Error generating report: {str(e)}")

def hide_iban(iban):
    iban = iban.replace(" ", "") 

    if len(iban) < 8:  
        return iban 

    country_code = iban[:4]
    last_digits = iban[-4:]
    middle_length = len(iban) - 8
    middle_masked = "*" * middle_length

    return country_code + middle_masked + last_digits
