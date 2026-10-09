from django.db import migrations

def seed_clavegueram_invoices_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    ReportType = apps.get_model('statistics', 'ReportType')
    
    try:
        billing_section = ReportType.objects.get(token='billing')
    except ReportType.DoesNotExist:
        return
        
    AvailableReport.objects.update_or_create(
        function_name='clavegueram_invoices_report',
        defaults={
            'name': 'Informe de clavegueram facturat',
            'description': 'Informe de clavegueram basat en les factures i no amb els moviments de cartera.',
            'section': billing_section,
            'download_button_name': 'Descarregar Excel',
            'has_custom_config': False,
            'required_fields': ['date_range', 'exploitation_id'],
            'position': 21,
            'is_active': True
        }
    )

def rollback_clavegueram_invoices_report(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='clavegueram_invoices_report').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0027_move_recaptacio_to_wallet'),
    ]

    operations = [
        migrations.RunPython(seed_clavegueram_invoices_report, rollback_clavegueram_invoices_report),
    ]
