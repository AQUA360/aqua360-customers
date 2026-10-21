"""Registra el resum de facturació per tarifa, tram i tarifa social.

Mateix resum que "Resum de facturació" (get_report_billing_summary), desglossat
per concepte, tarifa, tram i tarifa social, amb subtotals per producte. No pisa
cap AvailableReport existent: get_or_create per function_name.
"""

REPORT_DEFAULTS = {
    'name': 'Resum de facturació per tarifa, tram i tarifa social',
    'description': (
        "Resum de facturació desglossat per concepte, tarifa, tram i tarifa "
        "social: número de factures, unitats, base, IVA i totals, amb "
        "subtotals per producte que quadren amb el resum de facturació."
    ),
    'is_active': True,
    'download_button_name': 'Descarregar Excel',
    'has_custom_config': False,
    'required_fields': ['date_range', 'exploitation_id'],
}


def run():
    from django.db.models import Max

    from statistics.models import AvailableReport, ReportType

    billing_section = ReportType.objects.filter(token='billing').first()
    max_pos = (
        AvailableReport.objects.filter(section=billing_section)
        .aggregate(max_pos=Max('position'))
        .get('max_pos')
        or 0
    )

    report, created = AvailableReport.objects.get_or_create(
        function_name='billing_summary_by_rate_report',
        defaults={
            **REPORT_DEFAULTS,
            'section': billing_section,
            'position': max_pos + 1,
        },
    )
    if not created:
        for field, value in REPORT_DEFAULTS.items():
            setattr(report, field, value)
        if billing_section and report.section_id != billing_section.id:
            report.section = billing_section
        report.save()
