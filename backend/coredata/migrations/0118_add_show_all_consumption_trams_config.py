from django.db import migrations

def add_show_all_consumption_trams_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='SHOW_ALL_CONSUMPTION_TRAMS').exists():
        ConfigProject.objects.create(
            token='SHOW_ALL_CONSUMPTION_TRAMS',
            name="Mostrar tots els trams de consum a la factura",
            value='false',
            file='General'
        )

def remove_show_all_consumption_trams_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='SHOW_ALL_CONSUMPTION_TRAMS').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0117_address_address_extra'),
    ]

    operations = [
        migrations.RunPython(add_show_all_consumption_trams_config, remove_show_all_consumption_trams_config),
    ]
