from django.db import migrations

def create_incident_closed_status_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    IncidentStatus = apps.get_model('notification', 'IncidentStatus')
    
    # Intentar buscar el status "Tancada" o "Closed" per pouar-ne el seu token dinàmicament
    default_value = '2'
    try:
        status = IncidentStatus.objects.filter(name__icontains='Tancada').first()
        if not status:
            status = IncidentStatus.objects.filter(name__icontains='Closed').first()
        
        if status and status.token:
            default_value = status.token
    except Exception:
        pass
        
    ConfigProject.objects.get_or_create(
        token='incident_status_closed_token',
        defaults={
            'name': 'Incident Status Closed Token',
            'value': default_value
        }
    )

def reverse_incident_closed_status_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='incident_status_closed_token').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0098_merge_20260504_1038'),
        ('notification', '0006_incidentstatus_incidenttype_incident_incidentreport'), 
    ]

    operations = [
        migrations.RunPython(create_incident_closed_status_config, reverse_incident_closed_status_config),
    ]
