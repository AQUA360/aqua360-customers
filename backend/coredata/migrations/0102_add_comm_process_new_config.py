from django.db import migrations

def create_communication_process_new_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    
    ConfigProject.objects.get_or_create(
        token='communication_use_type_reading',
        defaults={
            'name': 'Token de tipo de uso de comunicación por lecturas',
            'value': 'reading'
        }
    )
    ConfigProject.objects.get_or_create(
        token='communication_process_status_draft_token',
        defaults={
            'name': 'Token de estado borrador de un proceso de comunicación',
            'value': '4'
        }
    )
    ConfigProject.objects.get_or_create(
        token='communication_process_status_finalized_token',
        defaults={
            'name': 'Token de estado finalizado de un proceso de comunicación',
            'value': '3'
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0101_alter_personcontact_email'),
    ]

    operations = [
        migrations.RunPython(create_communication_process_new_config),
    ]
