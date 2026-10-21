from django.db import migrations

def add_bail_return_invoice_disabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='BAIL_RETURN_INVOICE_DISABLED').exists():
        ConfigProject.objects.create(
            token='BAIL_RETURN_INVOICE_DISABLED',
            name='No generar factura de retorn de fiança (el retorn es completa sense factura)',
            value='false',
            file='General'
        )

def remove_bail_return_invoice_disabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='BAIL_RETURN_INVOICE_DISABLED').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0139_add_order_reason_configs'),
    ]

    operations = [
        migrations.RunPython(add_bail_return_invoice_disabled_config, remove_bail_return_invoice_disabled_config),
    ]
