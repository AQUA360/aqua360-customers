from django.db import migrations


def create_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token='giswater_supply_cut_sync_enabled',
        defaults={
            'name': "Mostrar el botó «Sincronitzar amb GIS Water» a la llista de talls de subministrament",
            'value': 'false',
        },
    )


def delete_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='giswater_supply_cut_sync_enabled').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0139_companybank_barcode_suffix'),
    ]

    operations = [
        migrations.RunPython(create_config, delete_config),
    ]
