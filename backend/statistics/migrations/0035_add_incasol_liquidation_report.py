from django.db import migrations


def add_incasol_liquidation_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    ReportType = apps.get_model('statistics', 'ReportType')

    billing_section = ReportType.objects.filter(token='billing').first()

    AvailableReport.objects.get_or_create(
        function_name='incasol_liquidation_report',
        defaults={
            'name': 'Liquidació de Fiances INCASOL',
            'description': (
                'Document de liquidació trimestral de fiances de lloguer en règim de concert, '
                'amb el resum d\'altes i baixes i el detall de moviments per contracte.'
            ),
            'is_active': True,
            'section': billing_section,
            'download_button_name': 'Descarregar TXT',
            'has_custom_config': False,
            'required_fields': ['date_range', 'exploitation_id'],
            'position': 21,
        }
    )


def remove_incasol_liquidation_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='incasol_liquidation_report').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0034_generalreport_filters_generalreport_filters_display_and_more'),
    ]

    operations = [
        migrations.RunPython(add_incasol_liquidation_report, remove_incasol_liquidation_report),
    ]
