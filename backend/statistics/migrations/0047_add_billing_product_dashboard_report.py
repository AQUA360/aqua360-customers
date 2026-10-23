from django.db import migrations


def add_billing_product_dashboard_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    ReportType = apps.get_model('statistics', 'ReportType')

    billing_section = ReportType.objects.filter(token='billing').first()

    AvailableReport.objects.get_or_create(
        function_name='billing_product_dashboard',
        defaults={
            'name': 'Dashboard de facturació',
            'description': (
                'Una fila per factura amb els imports agregats per producte '
                '(subtotal, IVA i total) i els camps de sector, tipus de pagament, '
                'tipus d\'ús, ús ACA, lectura estimada, observació, tarifa social '
                'i ampliació de trams.'
            ),
            'is_active': True,
            'section': billing_section,
            'download_button_name': 'Descarregar Excel',
            'has_custom_config': True,
            'required_fields': ['date_range', 'exploitation_id'],
            'position': 27,
        }
    )


def remove_billing_product_dashboard_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='billing_product_dashboard').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0046_vw_contract_debt_exclude_balance'),
    ]

    operations = [
        migrations.RunPython(
            add_billing_product_dashboard_report,
            remove_billing_product_dashboard_report,
        ),
    ]
