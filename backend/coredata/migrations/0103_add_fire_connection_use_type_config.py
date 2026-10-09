from django.db import migrations

def add_configs(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    
    # Ensure fire_usage_type_token exists
    ConfigProject.objects.get_or_create(
        token='fire_usage_type_token',
        defaults={
            'name': 'Token Tipus d\'ús Incendis (Contracte)',
            'value': 'inc'
        }
    )

    # Add fire_connection_use_type_token
    ConfigProject.objects.get_or_create(
        token='fire_connection_use_type_token',
        defaults={
            'name': 'Token Tipus d\'ús Incendis (Connexió)',
            'value': 'incendis'
        }
    )

def remove_configs(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token__in=['fire_connection_use_type_token']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0102_unusual_consumption_config'),
    ]

    operations = [
        migrations.RunPython(add_configs, remove_configs),
    ]
