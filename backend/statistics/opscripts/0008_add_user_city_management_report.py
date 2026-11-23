"""Registra l'informe de gestions per usuari i municipi.

Canvis de titular, sol·licituds d'alta, canvis de compte i de forma de pagament,
cobraments per forma de pagament i modificacions de factures, per a cada municipi
i usuari. No pisa cap AvailableReport existent: get_or_create per function_name.
"""

REPORT_DEFAULTS = {
    'name': 'Gestions per usuari i municipi',
    'description': (
        "Gestions fetes per cada usuari en el període, separades per municipi: canvis de "
        "titular, sol·licituds d'alta, canvis de número de compte i de forma de pagament, "
        "cobraments per forma de pagament, modificacions de factures i factures creades a mà. "
        "No compta els processos automàtics."
    ),
    'is_active': True,
    'download_button_name': 'Descarregar Excel',
    'has_custom_config': False,
    'required_fields': ['date_range'],
}


def run():
    from django.db.models import Max

    from statistics.models import AvailableReport, ReportType

    section = ReportType.objects.filter(token='statistics').first()
    max_pos = (
        AvailableReport.objects.filter(section=section)
        .aggregate(max_pos=Max('position'))
        .get('max_pos')
        or 0
    )

    report, created = AvailableReport.objects.get_or_create(
        function_name='user_city_management_report',
        defaults={
            **REPORT_DEFAULTS,
            'section': section,
            'position': max_pos + 1,
        },
    )
    if not created:
        for field, value in REPORT_DEFAULTS.items():
            setattr(report, field, value)
        if section and report.section_id != section.id:
            report.section = section
        report.save()
