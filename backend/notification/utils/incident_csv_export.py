import openpyxl
from io import BytesIO
from django.utils import timezone
from django.utils.translation import gettext as _
from statistics.views.reports_views import add_row, adjust_column_widths, black_fill, white_bold_font

def build_incident_export_csv_bytes(queryset):
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = _("Detall Registres")
    
    headers = [
        _('Referència'),
        _('Nom / Títol'),
        _('Estat'),
        _('Tipus d\'Incidència'),
        _('Referència Contracte'),
        _('Referència Factura'),
        _('Referència Ordre'),
        _('Data Creació'),
        _('Data Actualització'),
        _('Descripció')
    ]
    
    row = 0
    row = add_row(sheet, row, headers, fill=black_fill, font=white_bold_font)
    
    for incident in queryset.select_related('status', 'type', 'contract', 'invoice', 'order_incident').prefetch_related('orders').iterator(chunk_size=500):
        # Determine order token
        order_token = ''
        if incident.order_incident:
            order_token = incident.order_incident.token
        else:
            first_order = incident.orders.first()
            if first_order:
                order_token = first_order.token

        created_str = incident.created_at.strftime('%d/%m/%Y %H:%M:%S') if incident.created_at else ''
        updated_str = incident.updated_at.strftime('%d/%m/%Y %H:%M:%S') if incident.updated_at else ''
        
        row_values = [
            incident.token or '',
            incident.name or '',
            incident.status.name if incident.status else '',
            incident.type.name if incident.type else '',
            incident.contract.token if incident.contract else '',
            incident.invoice.token if incident.invoice else '',
            order_token or '',
            created_str,
            updated_str,
            incident.description or ''
        ]
        row = add_row(sheet, row, row_values)
        
    adjust_column_widths(sheet)
    
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
