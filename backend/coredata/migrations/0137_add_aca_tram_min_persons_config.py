from django.db import migrations

def add_aca_tram_min_persons_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='aca_tram_min_persons').exists():
        ConfigProject.objects.create(
            token='aca_tram_min_persons',
            name="Mínim de persones a l'habitatge per a l'ampliació de trams de l'ACA",
            value='4',
            file='ACA'
        )

def remove_aca_tram_min_persons_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='aca_tram_min_persons').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0136_add_change_meter_configs'),
    ]

    operations = [
        migrations.RunPython(add_aca_tram_min_persons_config, remove_aca_tram_min_persons_config),
    ]
