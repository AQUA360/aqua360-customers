import datetime
import logging
import zipfile
from io import BytesIO

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from billing.models import Invoice
from billing.utils.aca_company_service import ACACompanyError
from billing.utils.generate_factdeta_service import generate_factdeta_document
from service.models import Exploitation
from statistics.views.reports_views import save_report

logger = logging.getLogger(__name__)


def generate_factdeta_report(request, black_fill=None, white_bold_font=None, task=None):
    """Relació detallada de facturació (FACTDETA en baixa) d'un any: un fitxer per municipi,
    comprimits en un zip amb el resum de les validacions que cal revisar."""
    try:
        year = request.data.get('year') or request.data.get('model_347_year')
        if not year:
            return Response({"error": "year is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        year = int(year)

        exploitation_id = request.data.get('exploitation_id', None)
        exploitations = Exploitation.objects.filter(is_active=True)
        if exploitation_id:
            exploitations = exploitations.filter(id=exploitation_id)

        invoices = Invoice.objects.filter(is_active=True, issue_date__year=year)
        # Amb múltiples empreses cada fitxer ACA és d'una sola empresa (veure resolve_aca_company)
        company_id = request.data.get('company_id', None)
        if company_id:
            invoices = invoices.filter(company_id=company_id)

        try:
            files = generate_factdeta_document(exploitations, invoices)
        except ACACompanyError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST), None, None
        if not files:
            return None, None, None

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            warnings = []
            for file_data in files:
                zip_file.writestr(file_data["file_name"], file_data["content"])
                if file_data["warnings"]:
                    warnings.append(file_data["file_name"])
                    warnings += [f"  - {warning}" for warning in file_data["warnings"]]
            if warnings:
                zip_file.writestr(f"VALIDACIONS_FACTDETA_{year}.txt", "\n".join(warnings) + "\n")

        file_name = f"FACTDETA_{year}.zip"
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        document_id = save_report(
            content=buffer.getvalue(),
            filename=file_name,
            name=request.data.get('name', ''),
            type_id=request.data.get('type_id', None),
            start_date=datetime.date(year, 1, 1),
            end_date=datetime.date(year, 12, 31),
        )
        return response, document_id, None
    except Exception:
        logger.exception("Error inesperat")
        return Response({"error": "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
