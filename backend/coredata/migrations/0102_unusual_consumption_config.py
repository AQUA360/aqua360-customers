from django.db import migrations

def add_unusual_consumption_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='reading_alert_unusual_consumption_min_value').exists():
        ConfigProject.objects.create(
            token='reading_alert_unusual_consumption_min_value',
            name='Consum mínim per a l\'alerta de consum inusual',
            value='20',
            file='General'
        )

def remove_unusual_consumption_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='reading_alert_unusual_consumption_min_value').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0101_alter_personcontact_email'),
    ]

    operations = [
        migrations.RunPython(add_unusual_consumption_config, remove_unusual_consumption_config),
    ]
