from django.db import migrations


def add_factdeta_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    ReportType = apps.get_model('statistics', 'ReportType')

    # Mateixa secció que la declaració ACA
    aca_report = AvailableReport.objects.filter(function_name='aca_summary_report').first()
    section = aca_report.section if aca_report else ReportType.objects.filter(token='billing').first()

    AvailableReport.objects.get_or_create(
        function_name='factdeta_report',
        defaults={
            'name': "Relació detallada de facturació (FACTDETA)",
            'description': (
                "Fitxers FACTDETA en baixa de l'ACA (format 2026) d'un any de facturació, un per municipi, "
                "amb el resum de validacions a revisar abans de passar-los pel validador de l'ACA."
            ),
            'is_active': True,
            'section': section,
            'download_button_name': 'Descarregar zip',
            'has_custom_config': False,
            'required_fields': ['year', 'exploitation_id'],
            'position': 24,
        }
    )


def remove_factdeta_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='factdeta_report').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0050_add_incident_compliance_report'),
    ]

    operations = [
        migrations.RunPython(add_factdeta_report, remove_factdeta_report),
    ]
