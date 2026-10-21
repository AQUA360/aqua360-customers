import datetime
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from pricing.utils.accounting_service import generate_general_accounting
from statistics.views.reports_views import save_report



def generate_general_accounting_report(request, black_fill=None, white_bold_font=None, task=None):
    try:
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        start_date_raw = request.data.get('start_date')

        if not date_range and not start_date_raw:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None

        # generate_general_accounting expects start_date as YYYY-MM-DD and loads its own data
        if date_range:
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            request.data['start_date'] = end_date.strftime('%Y-%m-%d')
        else:
            start_date_str = str(start_date_raw)[:10]
            end_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
            request.data['start_date'] = start_date_str

        content_file = generate_general_accounting(request)

        filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        response = HttpResponse(content_file.getvalue(), content_type="text/plain")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        document_id = save_report(
            content=content_file.getvalue(), filename=filename, name=name, type_id=type_id,
            start_date=end_date, end_date=end_date,
        )

        return response, document_id, None

    except Exception as e:
        import traceback
        print("Error in generate_general_accounting_report: ", e)
        traceback.print_exc()
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None