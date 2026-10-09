from django.db import migrations

def add_ov_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='OV_ENABLED').exists():
        ConfigProject.objects.create(
            token='OV_ENABLED',
            name='Oficina Virtual Habilitada',
            value='true',
            file='General'
        )

def remove_ov_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='OV_ENABLED').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0087_address_city_name_address_province_name'),
    ]

    operations = [
        migrations.RunPython(add_ov_enabled_config, remove_ov_enabled_config),
    ]
