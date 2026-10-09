from django.db import migrations

def add_aca_notification_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='aca_notification_enabled').exists():
        ConfigProject.objects.create(
            token='aca_notification_enabled',
            name="Activa l'enviament de notificacions de bonificacions ACA (ampliació de trams)",
            value='false',
            file='ACA'
        )

def remove_aca_notification_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='aca_notification_enabled').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0124_fix_street_type_aca_abbreviation'),
    ]

    operations = [
        migrations.RunPython(add_aca_notification_enabled_config, remove_aca_notification_enabled_config),
    ]
