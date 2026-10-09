import os
import base64
from io import BytesIO
from datetime import datetime, timedelta

from django.conf import settings
from django.template import Template, Context
from django.core.files.base import ContentFile
from django.db.models.signals import post_save

from xhtml2pdf import pisa
from decouple import config

from coredata.models import ConfigProject
from coredata.serializers import AddressSerializer
from coredata.utils.address_utils import get_address_complete_without_city
from coredata.utils.template_utils import resolve_template_path


from documentmanager.utils.sign_certificate_service import sign_pdf
from documentmanager.utils.main_utils import upload_document

from service.models import Company
from service.serializers.company_serializer import CompanySerializer

from order.models import Order
from claimrequest.models import ClaimRequest


def generate_order_pdf(order, request=None, context=None, save_pdf=True):
    
    try:
        print('[utils/order_pdf.py] generate order pdf')

        claim_request = order.claim_request if hasattr(order, 'claim_request') else None
        if order.contract:
            contract = order.contract
        elif order.contract_request:
            contract = order.contract_request
        elif order.contract_termination_request:
            contract = order.contract_termination_request.contract
        else:
            contract = None
        supply_point = order.supply_point if hasattr(order, 'supply_point') else None
        order_type = order.type if hasattr(order, 'type') else None
        order_status = order.status if hasattr(order, 'status') else None
        order_operators = order.operators.all() if hasattr(order, 'operators') else None

        company_obj = None

        if contract and hasattr(contract, 'exploitation') and contract.exploitation and contract.exploitation.company:
            company_obj = contract.exploitation.company
        elif claim_request and hasattr(claim_request, 'company') and claim_request.company:
            company_obj = claim_request.company
        else:
            company_obj = Company.objects.first()

        company = CompanySerializer(company_obj, context=context).data if company_obj else None

        # Logo
        logo = company_obj.logo.path if company_obj and company_obj.logo else None

        physical_address = None
        physical_location = None
        physical_person = None

        if contract and getattr(contract, 'address_contact', None):
            ac = contract.address_contact
            if ac.address:
                physical_address = get_address_complete_without_city(ac.address)
                physical_location = f"{ac.address.postal_code} {ac.address.city.name}"
            if ac.person:
                physical_person = str(ac.person)

        if not physical_person and claim_request and getattr(claim_request, 'customer', None):
            physical_person = str(claim_request.customer)

        supply_address = None
        if supply_point and getattr(supply_point, 'address', None):
            supply_address = AddressSerializer(supply_point.address).data

        main_color = "#074df0"
        secondary_color = "#ffffff"
        try:
            main_color = ConfigProject.objects.get(token='invoice_main_color').value
            secondary_color = ConfigProject.objects.get(token='invoice_secondary_color').value
        except Exception:
            pass

        document_type_label = "ORDRE"
        try:
            order_type_label_token = ConfigProject.objects.get(token='order_document_type_label').value
            document_type_label = order_type_label_token
        except Exception:
            pass

        html_template = None

        if not html_template:
            order_lang = getattr(contract, 'language', None) or settings.LANGUAGE_CODE
            file_name = resolve_template_path('order/templates/order_template.html', lang=order_lang)
            with open(file_name, 'r', encoding='utf-8') as f:
                html_template = f.read()

        django_template = Template(html_template)

        context_data = {
            'order': order,
            'order_type': order_type,
            'order_status': order_status,
            'order_operators': order_operators,
            'claim_request': claim_request,
            'contract': contract,
            'supply_point': supply_point,
            'company': company,
            'logo': logo,
            'main_color': main_color,
            'secondary_color': secondary_color,
            'supply_address': supply_address,
            'now': datetime.now(),
            'data_protection_law_text': company.get('data_protection_law_text') if company else None,
        }

        ctx = Context(context_data)
        html_rendered = django_template.render(ctx)

        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_rendered, dest=pdf_buffer)
        if pisa_status.err:
            raise Exception(f"Error PISA en generar el PDF d'ordre: {str(pisa_status.err)}")

        order_prefix = order.type.token.upper() if order_type else "ORD"
        pdf_filename = f"{order_prefix}_{order.id}.pdf"

        """ try:
            bg_img = os.path.join("config", "assets", "watermark.png")
            pdf_buffer = add_watermark_to_pdf(pdf_buffer, bg_img, True)
        except Exception as e:
            print(f"Error en afegir el fons a l'ordre: {str(e)}")

        test_watermark_path = None
        try:
            if config('ENV', default='-').upper() in ['TEST', 'LOCAL']:
                test_watermark_path = os.path.join("config", "assets", "test-watermark.png")
                pdf_buffer = add_watermark_to_pdf(pdf_buffer, test_watermark_path, opacity=0.1)
        except Exception:
            pass """


        final_pdf_buffer = pdf_buffer 

        document_id = None
        if save_pdf:
            service = settings.DOCUMENT_MANAGER_SERVICES.get("order")

            customer_token = None
            if contract and getattr(contract, 'customer', None):
                customer_token = getattr(contract.customer, 'token', None)
            elif claim_request and getattr(claim_request, 'customer', None):
                customer_token = getattr(claim_request.customer, 'token', None)

            document_file = upload_document(
                ContentFile(final_pdf_buffer.getvalue(), name=pdf_filename),
                'ORDRES',
                document_type_label,
                order.id,
                customer_token or '',
                '',
                service,
                pdf_filename
            )

            order.order_file = document_file
            order.save()
            document_id = document_file.id

        file_url = None
        if order.order_file and order.order_file.location:
            location = order.order_file.location

            base_dir_str = str(settings.BASE_DIR)

            if isinstance(location, str) and location.startswith(base_dir_str):
                relative = location.replace(base_dir_str, "").lstrip("/")
            else:
                relative = location.lstrip("/")

            base = settings.DOMAIN_MEDIA or ""
            file_url = f"{base}/media/documents/{relative}"



        return file_url, document_id, final_pdf_buffer



    except Exception as e:
        error_msg = f"Error en generar el PDF d'ordre: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
