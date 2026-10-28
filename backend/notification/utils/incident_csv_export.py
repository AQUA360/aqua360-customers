import openpyxl
from io import BytesIO
from django.utils import timezone
from django.utils.translation import gettext as _
from statistics.views.reports_views import add_row, adjust_column_widths, black_fill, white_bold_font

def _datetime_str(value):
    return timezone.localtime(value).strftime('%d/%m/%Y %H:%M:%S') if value else ''


def build_incident_export_csv_bytes(queryset, query_params=None, user=None):
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
        _('Descripció'),
        _('Creada per'),
        _('Assignada a'),
        _('Data Venciment'),
        _('Data Tancament'),
        _('Resolució'),
        _('Tall de Subministrament'),
        _('Canal'),
        _('Primera Resposta'),
        _('Dins de Termini'),
        _('Fase'),
    ]
    
    row = 0
    row = add_row(sheet, row, headers, fill=black_fill, font=white_bold_font)
    
    for incident in queryset.select_related('status', 'type', 'contract', 'invoice', 'order_incident', 'created_by', 'assigned_to', 'supply_cut', 'channel').prefetch_related('orders').iterator(chunk_size=500):
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
        on_time = incident.closed_on_time
        on_time_str = '' if on_time is None else (_('Sí') if on_time else _('No'))
        
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
            incident.description or '',
            incident.created_by.username if incident.created_by else '',
            incident.assigned_to.username if incident.assigned_to else '',
            _datetime_str(incident.due_at),
            _datetime_str(incident.closed_at),
            incident.resolution or '',
            incident.supply_cut.token if incident.supply_cut else '',
            incident.channel.name if incident.channel else '',
            _datetime_str(incident.first_response_at),
            on_time_str,
            incident.status.get_phase_display() if incident.status and incident.status.phase else '',
        ]
        row = add_row(sheet, row, row_values)
        
    adjust_column_widths(sheet)
    
    # Dades de l'extracció, per a l'auditoria: quan, qui i amb quins filtres
    info = wb.create_sheet(title=_("Extracció"))
    info_row = add_row(info, 0, [_('Data d\'extracció'), timezone.localtime().strftime('%d/%m/%Y %H:%M:%S')])
    info_row = add_row(info, info_row, [_('Usuari'), user.username if user else ''])
    info_row = add_row(info, info_row, [_('Registres'), row - 1])
    for key, value in (query_params or {}).items():
        if value not in (None, ''):
            info_row = add_row(info, info_row, [key, str(value)])
    adjust_column_widths(info)
    
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
