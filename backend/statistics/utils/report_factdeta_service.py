import datetime
import logging
import zipfile
from io import BytesIO

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from billing.models import Invoice
from billing.utils.aca_company_service import ACACompanyError
from billing.utils.generate_factdeta_service import FactdetaValidationError, generate_factdeta_document
from service.models import Exploitation
from statistics.views.reports_views import save_report

logger = logging.getLogger(__name__)


def _parse_report_date(value):
    """Data del filtre de la pàgina d'informes (ISO amb hora, com la Declaració ACA) o AAAA-MM-DD."""
    try:
        return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ').date()
    except ValueError:
        return datetime.date.fromisoformat(value[:10])


def generate_factdeta_report(request, black_fill=None, white_bold_font=None, task=None):
    """Relació detallada de facturació (FACTDETA en baixa) d'un any, o de les factures emeses dins el
    filtre de dates: un fitxer per municipi i any, comprimits en un zip amb el resum de les validacions
    que cal revisar."""
    try:
        date_range = request.data.get('date_range')
        if date_range:
            # Filtre de dates de la pàgina d'informes: les factures emeses dins el període, interpretat
            # igual que a la Declaració ACA perquè els dos informes es puguin comparar
            try:
                start_date, end_date = (_parse_report_date(value) for value in date_range[:2])
            except (TypeError, ValueError):
                return Response({"error": "date_range must be two dates."}, status=status.HTTP_400_BAD_REQUEST), None, None
            invoices = Invoice.objects.filter(is_active=True, issue_date__range=(start_date, end_date))
            label = f"{start_date:%Y%m%d}_{end_date:%Y%m%d}"
        else:
            year = request.data.get('year') or request.data.get('model_347_year')
            if not year:
                return Response({"error": "year or date_range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
            try:
                year = int(year)
            except (TypeError, ValueError):
                return Response({"error": "year must be a number."}, status=status.HTTP_400_BAD_REQUEST), None, None
            start_date, end_date = datetime.date(year, 1, 1), datetime.date(year, 12, 31)
            invoices = Invoice.objects.filter(is_active=True, issue_date__year=year)
            label = str(year)
        # Amb múltiples empreses cada fitxer ACA és d'una sola empresa (veure resolve_aca_company)
        company_id = request.data.get('company_id', None)
        if company_id:
            invoices = invoices.filter(company_id=company_id)

        # També les explotacions desactivades que tenen factures de l'any
        exploitation_id = request.data.get('exploitation_id', None)
        exploitations = Exploitation.objects.filter(Q(is_active=True) | Q(id__in=invoices.values('exploitation_id')))
        if exploitation_id:
            exploitations = exploitations.filter(id=exploitation_id)
            # Que les factures d'altres explotacions (o sense) no bloquegin el fitxer del municipi demanat
            invoices = invoices.filter(exploitation_id=exploitation_id)

        try:
            files = generate_factdeta_document(exploitations, invoices)
        except (ACACompanyError, FactdetaValidationError) as e:
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
                zip_file.writestr(f"VALIDACIONS_FACTDETA_{label}.txt", "\n".join(warnings) + "\n")

        # Amb data i hora perquè dues execucions del mateix període no comparteixin el nom del fitxer desat
        file_name = f"FACTDETA_{label}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        document_id = save_report(
            content=buffer.getvalue(),
            filename=file_name,
            name=request.data.get('name', ''),
            type_id=request.data.get('type_id', None),
            start_date=start_date,
            end_date=end_date,
        )
        return response, document_id, None
    except Exception:
        logger.exception("Error inesperat")
        return Response({"error": "Ha ocorregut un error inesperat."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
