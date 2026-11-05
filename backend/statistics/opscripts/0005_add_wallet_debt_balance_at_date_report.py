"""Registra l'informe de deute i saldo per contracte a una data de tall (secció de cobraments).

Per a cada contracte retorna el saldo positiu de la guardiola i el deute pendent tal com
estaven a la data indicada. No pisa cap AvailableReport existent: get_or_create per
function_name.
"""

REPORT_DEFAULTS = {
    'name': 'Deute i saldo per contracte a data',
    'description': (
        "Per a cada contracte amb saldo o deute, el saldo positiu de la guardiola i el "
        "deute pendent (pagaments pendents, processats, vençuts, retornats o en "
        "morositat) a la data de tall indicada."
    ),
    'is_active': True,
    'download_button_name': 'Descarregar Excel',
    'has_custom_config': False,
    'required_fields': ['cutoff_date', 'exploitation_id'],
}


def run():
    from django.db.models import Max

    from statistics.models import AvailableReport, ReportType

    wallet_section = ReportType.objects.filter(token='wallet').first()
    max_pos = (
        AvailableReport.objects.filter(section=wallet_section)
        .aggregate(max_pos=Max('position'))
        .get('max_pos')
        or 0
    )

    report, created = AvailableReport.objects.get_or_create(
        function_name='wallet_debt_balance_at_date_report',
        defaults={
            **REPORT_DEFAULTS,
            'section': wallet_section,
            'position': max_pos + 1,
        },
    )
    if not created:
        for field, value in REPORT_DEFAULTS.items():
            setattr(report, field, value)
        if wallet_section and report.section_id != wallet_section.id:
            report.section = wallet_section
        report.save()
