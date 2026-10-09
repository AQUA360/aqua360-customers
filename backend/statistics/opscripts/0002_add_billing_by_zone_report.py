"""Registra l'informe d'execució de padrons per zona de tarificació.

Les zones són les SupplyPointPlacement del client (i les que surtin a les
factures). No pisa cap AvailableReport existent: get_or_create per
function_name.
"""

REPORT_DEFAULTS = {
    'name': 'Execució de padrons per zona de tarificació',
    'description': (
        "Ingressos i consums d'aigua desglossats per cada padró "
        "inclòs al filtre (facturació seleccionada o període) i per zona "
        "(placement del punt de subministrament): quota de servei, m³ per "
        "tram, clavegueram i cànon ACA (CANON-DOM, CANON-MUN, CANON-HOTELS, "
        "CANON-IND) també per trams."
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
        function_name='billing_by_zone_report',
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
