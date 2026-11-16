import datetime
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from pricing.utils.accounting_service import generate_general_accounting
from statistics.views.reports_views import add_row, adjust_column_widths, save_report, jump_row
import logging

logger = logging.getLogger(__name__)



def _parse_report_date(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if 'T' in text:
        # Accept both ...Z and ...+00:00 / naive ISO datetimes.
        normalized = text.replace('Z', '+00:00')
        try:
            return datetime.datetime.fromisoformat(normalized)
        except ValueError:
            pass
        for fmt in ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
            try:
                return datetime.datetime.strptime(text, fmt)
            except ValueError:
                continue
    return datetime.datetime.strptime(text[:10], '%Y-%m-%d')


def generate_general_accounting_report(request, black_fill=None, white_bold_font=None, task=None):
    try:
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        start_date_raw = request.data.get('start_date')
        end_date_raw = request.data.get('end_date')

        if not date_range and not start_date_raw:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None

        # generate_general_accounting expects start_date/end_date as YYYY-MM-DD and loads its own data
        if date_range:
            start_dt = _parse_report_date(date_range[0])
            end_dt = _parse_report_date(date_range[1])
        else:
            start_dt = _parse_report_date(start_date_raw)
            end_dt = _parse_report_date(end_date_raw) if end_date_raw else start_dt

        if start_dt is None or end_dt is None:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None

        if end_dt < start_dt:
            start_dt, end_dt = end_dt, start_dt

        request.data['start_date'] = start_dt.strftime('%Y-%m-%d')
        request.data['end_date'] = end_dt.strftime('%Y-%m-%d')

        content_file = generate_general_accounting(request)
        if content_file is None:
            return None, None, None

        filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        response = HttpResponse(content_file.getvalue(), content_type="text/plain")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        document_id = save_report(
            content=content_file.getvalue(), filename=filename, name=name, type_id=type_id,
            start_date=start_dt, end_date=end_dt,
        )

        return response, document_id, None

    except Exception as e:
        logger.exception("Error inesperat")
        import traceback
        print("Error in generate_general_accounting_report: ", e)
        traceback.print_exc()
        return Response({"error": "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None