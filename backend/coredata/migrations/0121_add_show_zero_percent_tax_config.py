from django.db import migrations

def add_show_zero_percent_tax_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='SHOW_ZERO_PERCENT_TAX').exists():
        ConfigProject.objects.create(
            token='SHOW_ZERO_PERCENT_TAX',
            name="Mostrar el tram d'IVA al 0% al resum de la factura",
            value='false',
            file='Billing'
        )

def remove_show_zero_percent_tax_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='SHOW_ZERO_PERCENT_TAX').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0120_alter_personcontact_person'),
    ]

    operations = [
        migrations.RunPython(add_show_zero_percent_tax_config, remove_show_zero_percent_tax_config),
    ]
