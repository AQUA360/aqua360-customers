from datetime import datetime
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.db.models import Q
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from billing.models import Payment
from coredata.models import ConfigProject
from coredata.serializers import AddressSerializer
from documentmanager.utils.sign_certificate_service import sign_pdf
from service.serializers.company_serializer import CompanySerializer
from service.utils.exploitation_logo import exploitation_logo_source


def _resolve_contract_from_payment(payment):
    invoice = payment.invoice
    commitment_deposit = payment.commitment_deposit
    contract = None
    if invoice:
        if invoice.contract:
            contract = invoice.contract
        elif invoice.contract_request:
            contract = invoice.contract_request
        elif invoice.contract_termination:
            contract = invoice.contract_termination.contract
    if commitment_deposit:
        contract = commitment_deposit.contract
    return contract, invoice, commitment_deposit


def _contract_token(contract, payment):
    if contract:
        return getattr(contract, 'token', '') or ''
    return payment.customer_token_final or ''


def _supply_address_complete(contract):
    if not contract or not getattr(contract, 'supply_point_default', None):
        return ''
    supply_point = contract.supply_point_default
    if not supply_point or not supply_point.address:
        return ''
    return AddressSerializer(supply_point.address).data.get('address_complete', '') or ''


def _payment_reference(invoice, commitment_deposit):
    if invoice:
        return invoice.serie_final or ''
    if commitment_deposit:
        return commitment_deposit.token or ''
    return ''


def _exploitation_from_payment(invoice, commitment_deposit):
    if invoice:
        return invoice.exploitation
    if commitment_deposit:
        first_invoice = commitment_deposit.invoices.first()
        if first_invoice:
            return first_invoice.exploitation
    return None


def build_payment_proof_line(payment, observation=None):
    contract, invoice, commitment_deposit = _resolve_contract_from_payment(payment)
    return {
        'contract_token': _contract_token(contract, payment),
        'supply_address': _supply_address_complete(contract),
        'period': payment.payment_date,
        'reference': _payment_reference(invoice, commitment_deposit),
        'amount': payment.amount or Decimal('0'),
        'observation': observation,
    }


def build_payment_proof_context(payments, request, payment_date=None, observation=None):
    if not payments:
        raise ValueError('At least one payment is required')
    
    print("payments: ", payments)
    print("payment_date: ", payment_date)
    print("observation: ", observation)

    first_payment = payments[0]
    _, first_invoice, first_commitment = _resolve_contract_from_payment(first_payment)
    
    exploitation = _exploitation_from_payment(first_invoice, first_commitment)
    if not exploitation:
        raise ValueError('Could not resolve exploitation for payment proof')

    # if payments and len(payments) > 1:
    #     payments never have company related
    #     company = CompanySerializer(payments[0].company, context={'request': request}).data
    # else:
    #     company = CompanySerializer(exploitation.company, context={'request': request}).data
    company = CompanySerializer(exploitation.company, context={'request': request}).data

    logo = company['logo']
    if logo and not logo.startswith('http'):
        logo = request.build_absolute_uri(logo)
        logo = logo.replace('https', 'http')

    domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''
    exploitation_image = exploitation_logo_source(exploitation)
    now_date = datetime.now().date()
    if payment_date:
        now_date = datetime.strptime(payment_date, '%Y-%m-%d').date()

    

    main_color = '#074df0'
    secondary_color = '#ffffff'
    try:
        main_color = company['invoice_main_color'] or ConfigProject.objects.get(token='invoice_main_color').value
        secondary_color = company['invoice_secondary_color'] or ConfigProject.objects.get(token='invoice_secondary_color').value
    except ConfigProject.DoesNotExist:
        pass

    payment_lines = [
        build_payment_proof_line(payment, observation=observation)
        for payment in payments
    ]
    total_amount = sum((line['amount'] for line in payment_lines), Decimal('0'))
    return {
        'payment_lines': payment_lines,
        'total_amount': total_amount,
        'now_date': now_date,
        'company': company,
        'exploitation_image': exploitation_image,
        'main_color': main_color,
        'observation': observation,
        'secondary_color': secondary_color,
        'logo': logo,
        'exploitation': exploitation,
    }


def payment_proof_pdf_filename(now_date, payment_lines):
    first_ref = (payment_lines[0]['reference'] or 'payment').replace('/', '')
    if len(payment_lines) > 1:
        first_ref = f"{first_ref}_+{len(payment_lines) - 1}"
    return f"{now_date.strftime('%m%d')}_{first_ref}.pdf"


def render_payment_proof_pdf(payments, request, payment_date=None, observation=None):
    context = build_payment_proof_context(
        payments,
        request,
        payment_date=payment_date,
        observation=observation,
    )
    
    html_content = render_to_string('payment_proof_template.html', context)
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        raise RuntimeError('PDF generation failed')

    signed_pdf_buffer = sign_pdf(pdf_buffer, context['exploitation'].company, '', '')
    filename = payment_proof_pdf_filename(context['now_date'], context['payment_lines'])
    return signed_pdf_buffer, filename


def get_payments_from_request_data(data):
    payment_ids = data.get('ids')
    if payment_ids:
        if not isinstance(payment_ids, list):
            payment_ids = [payment_ids]
    else:
        payment_id = data.get('id')
        payment_ids = [payment_id] if payment_id else []

    payment_ids = [int(pid) for pid in payment_ids if pid is not None]
    if not payment_ids:
        return []

    payments_qs = Payment.objects.select_related(
        'invoice',
        'invoice__contract',
        'invoice__contract_request',
        'invoice__contract_termination',
        'invoice__exploitation',
        'commitment_deposit',
        'commitment_deposit__contract',
        'commitment_deposit__contract__supply_point_default__address',
    ).filter(id__in=payment_ids)
    payments_by_id = {payment.id: payment for payment in payments_qs}
    return [payments_by_id[payment_id] for payment_id in payment_ids if payment_id in payments_by_id]
