from decimal import Decimal
from io import BytesIO

from django.template.loader import render_to_string
from xhtml2pdf import pisa

from billing.models import Invoice
from coredata.models import ConfigProject
from service.utils.exploitation_logo import exploitation_logo_source


def get_general_invoice_group(invoice):
    """Totes les factures del mateix grup (contractes agrupats) i de la mateixa facturació."""
    contract_ids = list(invoice.general_contracts.values_list('id', flat=True))
    if not invoice.is_general or not contract_ids:
        return Invoice.objects.none()

    invoices = Invoice.objects.filter(
        is_active=True,
        is_general=True,
        is_suppressed=False,
        contract_id__in=contract_ids,
        type=invoice.type,
    )
    if invoice.billing_id:
        invoices = invoices.filter(billing_id=invoice.billing_id)
    else:
        invoices = invoices.filter(
            billing__isnull=True,
            billing_period_year=invoice.billing_period_year,
            billing_period_month=invoice.billing_period_month,
        )

    cancelled_token = ConfigProject.objects.filter(token='invoice_status_cancelled_token').values_list('value', flat=True).first()
    if cancelled_token:
        invoices = invoices.exclude(status__token=cancelled_token)

    return invoices.select_related(
        'contract', 'contract__supply_point_default__address', 'billing', 'exploitation', 'company'
    ).order_by('contract__token')


def generate_general_invoice_summary_pdf(invoice):
    """Genera el PDF resum d'una factura agrupada. Retorna (bytes, nom del fitxer)."""
    invoices = list(get_general_invoice_group(invoice))
    if not invoices:
        raise ValueError("La factura no pertany a cap grup de facturació agrupada")

    rows = []
    subtotal_sum = Decimal('0')
    total_sum = Decimal('0')
    for inv in invoices:
        supply_point = inv.contract.supply_point_default if inv.contract else None
        subtotal = inv.subtotal_final or Decimal('0')
        total = inv.total_final or Decimal('0')
        rows.append({
            'contract_token': inv.contract.token if inv.contract else '-',
            'serie': inv.serie_final or '-',
            'supply_address': str(supply_point.address) if supply_point and supply_point.address else '-',
            'subtotal': subtotal,
            'total': total,
        })
        subtotal_sum += subtotal
        total_sum += total

    colors = dict(ConfigProject.objects.filter(token__in=['invoice_main_color', 'invoice_secondary_color']).values_list('token', 'value'))
    company = invoice.company
    main_color = (company.invoice_main_color if company else None) or colors.get('invoice_main_color') or '#eaf0f2'
    secondary_color = (company.invoice_secondary_color if company else None) or colors.get('invoice_secondary_color') or '#074df0'

    html_rendered = render_to_string('general_invoice_summary_template.html', {
        'rows': rows,
        'subtotal_sum': subtotal_sum,
        'total_sum': total_sum,
        'title': invoice.billing.name if invoice.billing else invoice.title_final,
        'payer': invoice.payer_final or invoice.customer_final,
        'issue_date': invoice.issue_date,
        'company': invoice.company,
        'logo': exploitation_logo_source(invoice.exploitation),
        'main_color': main_color,
        'secondary_color': secondary_color,
    })

    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_rendered, dest=pdf_buffer)
    if pisa_status.err:
        raise Exception("PDF generation failed")

    period = invoice.issue_date.strftime('%Y%m') if invoice.issue_date else str(invoice.id)
    return pdf_buffer.getvalue(), f"resum_factures_agrupades_{period}.pdf"
