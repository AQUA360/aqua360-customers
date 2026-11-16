"""Activa la descàrrega en PDF per als informes pensats per presentar.

Només activa el flag `allow_pdf_export`: no el desactiva en cap altre informe, així que
es respecten els informes que ja s'hagin activat a mà des de l'admin.
"""

PDF_EXPORT_REPORTS = [
    'get_report_billing_summary',
    'billing_summary_by_rate_report',
    'detailed_typology_periodicity_report',
    'claim_response_time_report',
    'social_tariff_evolution_report',
]


def run():
    from statistics.models import AvailableReport

    AvailableReport.objects.filter(
        function_name__in=PDF_EXPORT_REPORTS,
    ).update(allow_pdf_export=True)
