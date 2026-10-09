import datetime
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from billing.utils.wincen_service import generate_wincen_file
from statistics.views.reports_views import save_report


def generate_wincen_export_report(request, black_fill=None, white_bold_font=None, task=None):
    billing_id = request.data.get('id') or request.data.get('billing_id')
    date_range = request.data.get('date_range')
    name = request.data.get('name', 'Exportació WinCen')

    start_date = None
    end_date = None

    if billing_id:
        try:
            billing_id = int(billing_id)
        except (TypeError, ValueError):
            return Response({'error': 'El camp id ha de ser un enter.'}, status=status.HTTP_400_BAD_REQUEST), None, None
    elif date_range and isinstance(date_range, list) and len(date_range) >= 2:
        try:
            start_date = datetime.datetime.strptime(date_range[0][:10], '%Y-%m-%d').date()
            end_date = datetime.datetime.strptime(date_range[1][:10], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return Response({'error': 'Format de dates incorrecte. Usa ISO 8601.'}, status=status.HTTP_400_BAD_REQUEST), None, None
    else:
        return Response(
            {'error': 'Cal indicar id (billing_id) o date_range.'},
            status=status.HTTP_400_BAD_REQUEST,
        ), None, None

    def _progress_callback(current, total):
        if task:
            task.update_state(
                state='PROGRESS',
                meta={
                    'current': current,
                    'total': total,
                    'percent': round((current / total) * 100, 2) if total else 0.0
                }
            )

    file_content = generate_wincen_file(
        billing_id=billing_id,
        start_date=start_date,
        end_date=end_date,
        include_readings=True,
        include_payments=True,
        progress_callback=_progress_callback if task else None,
    )

    suffix = str(billing_id) if billing_id else f'{start_date}_{end_date}'
    filename = f'wincen_{suffix}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.dat'

    document_id = save_report(
        content=file_content,
        filename=filename,
        name=name,
        type_id=None,
        start_date=start_date,
        end_date=end_date,
    )

    response = HttpResponse(
        file_content.encode('utf-8'),
        content_type='application/octet-stream',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response, document_id, filename
