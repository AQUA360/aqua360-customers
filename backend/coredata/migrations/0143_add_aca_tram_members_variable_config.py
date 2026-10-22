from django.db import migrations

CONFIG_TOKEN = 'aca_tram_members_variable_token'
CONFIG_NAME = "Variable de persones (total_persons) de l'ampliació de trams ACA"
DEFAULT_VALUE = 'ACA-TRAM-MEMBRES'


def add_aca_tram_members_variable_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    config, created = ConfigProject.objects.get_or_create(
        token=CONFIG_TOKEN,
        defaults={'name': CONFIG_NAME, 'value': DEFAULT_VALUE, 'file': 'ACA'},
    )
    if not created and not (config.value or '').strip():
        config.value = DEFAULT_VALUE
        config.save(update_fields=['value'])


def remove_aca_tram_members_variable_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0142_merge_20261021_1259'),
    ]

    operations = [
        migrations.RunPython(
            add_aca_tram_members_variable_config,
            remove_aca_tram_members_variable_config,
        ),
    ]
