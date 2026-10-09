from django.db import migrations


def add_wincen_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    ReportType = apps.get_model('statistics', 'ReportType')

    billing_section = ReportType.objects.filter(token='billing').first()

    AvailableReport.objects.get_or_create(
        function_name='wincen_export_report',
        defaults={
            'name': 'Exportació WinCen',
            'description': (
                'Genera el fitxer d\'exportació WinCen (format pipe-delimitat) per a una facturació. '
                'Inclou els registres ABONA, COMPT, LECTU, FACTU, LINFA i PAGAM de totes les factures actives.'
            ),
            'is_active': True,
            'section': billing_section,
            'download_button_name': 'Descarregar WinCen',
            'has_custom_config': False,
            'required_fields': ['date_range'],
            'position': 99,
        }
    )


def remove_wincen_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='wincen_export_report').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0029_reportqueue'),
    ]

    operations = [
        migrations.RunPython(add_wincen_report, remove_wincen_report),
    ]
