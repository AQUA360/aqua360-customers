import datetime
import logging
import zipfile
from io import BytesIO

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from billing.utils.aca_company_service import ACACompanyError
from billing.utils.factdeta_reader import build_factdeta_workbook, read_factdeta
from billing.utils.generate_factdeta_service import FactdetaValidationError, generate_factdeta_document
from service.models import Exploitation
from statistics.utils.report_filters import get_multi_ids, invoice_multi_filter_q
from statistics.utils.aca_declaration_service import aca_declaration_selection
from statistics.views.reports_views import save_report

logger = logging.getLogger(__name__)


def _summary_file_name(file_name):
    return f"RESUM_{file_name.rsplit('.', 1)[0]}.xlsx"


def _factdeta_summary_xlsx(file_data):
    """Resum de totals i validacions llegit del mateix .txt, per revisar-lo sense dependre del generador.
    És un afegit: si falla, el zip surt igualment amb el FACTDETA (None)."""
    try:
        buffer = BytesIO()
        build_factdeta_workbook(read_factdeta(file_data["content"], file_data["file_name"])).save(buffer)
        return buffer.getvalue()
    except Exception:
        logger.exception("No s'ha pogut generar el resum de %s", file_data["file_name"])
        return None


def _parse_report_date(value):
    """Data del filtre de la pàgina d'informes (ISO amb hora en UTC, com la Declaració ACA) o AAAA-MM-DD.
    Qualsevol altre format llança ValueError."""
    if len(value) == 10:
        return datetime.date.fromisoformat(value)
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).date()


def generate_factdeta_report(request, black_fill=None, white_bold_font=None, task=None):
    """Relació detallada de facturació (FACTDETA en baixa) d'un any, o de les factures emeses dins el
    filtre de dates: un fitxer per municipi i any, comprimits en un zip amb els resums i les validacions."""
    try:
        date_range = request.data.get('date_range')
        if date_range:
            # Filtre de dates de la pàgina d'informes: les factures emeses dins el període, interpretat
            # igual que a la Declaració ACA perquè els dos informes es puguin comparar
            try:
                start_date, end_date = (_parse_report_date(value) for value in date_range[:2])
            except (TypeError, ValueError):
                return Response({"error": "date_range must be two dates."}, status=status.HTTP_400_BAD_REQUEST), None, None
            if start_date > end_date:
                return Response({"error": "date_range start must not be after end."}, status=status.HTTP_400_BAD_REQUEST), None, None
            label = f"{start_date:%Y%m%d}_{end_date:%Y%m%d}"
        else:
            year = request.data.get('year') or request.data.get('model_347_year')
            if not year:
                return Response({"error": "year or date_range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
            try:
                year = int(year)
            except (TypeError, ValueError):
                return Response({"error": "year must be a number."}, status=status.HTTP_400_BAD_REQUEST), None, None
            if not 1 <= year <= 9999:
                return Response({"error": "year must be between 1 and 9999."}, status=status.HTTP_400_BAD_REQUEST), None, None
            start_date, end_date = datetime.date(year, 1, 1), datetime.date(year, 12, 31)
            label = str(year)
        # Les mateixes factures i línies de cànon que la Declaració ACA (A1) per dates, perquè els dos
        # informes quadrin: els mesos ja presentats, tal com es van declarar
        aca_selection = aca_declaration_selection(start_date, end_date, request)
        invoices = aca_selection.invoices
        # Amb múltiples empreses cada fitxer ACA és d'una sola empresa (veure resolve_aca_company)
        company_id = request.data.get('company_id', None)
        if company_id:
            invoices = invoices.filter(company_id=company_id)
        # Filtres múltiples de la pàgina d'informes (empreses, lots, abonats...), com a la Declaració ACA
        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        # També les explotacions desactivades que tenen factures de l'any
        exploitation_id = request.data.get('exploitation_id', None)
        exploitations = Exploitation.objects.filter(Q(is_active=True) | Q(id__in=invoices.values('exploitation_id')))
        if exploitation_id:
            exploitations = exploitations.filter(id=exploitation_id)
            # Que les factures d'altres explotacions (o sense) no bloquegin el fitxer del municipi demanat
            invoices = invoices.filter(exploitation_id=exploitation_id)

        try:
            files = generate_factdeta_document(exploitations, invoices, line_items_q=aca_selection.line_items_q)
        except (ACACompanyError, FactdetaValidationError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST), None, None
        if not files:
            return None, None, None

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            warnings = []
            for file_data in files:
                zip_file.writestr(file_data["file_name"], file_data["content"])
                summary = _factdeta_summary_xlsx(file_data)
                if summary:
                    zip_file.writestr(_summary_file_name(file_data["file_name"]), summary)
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
