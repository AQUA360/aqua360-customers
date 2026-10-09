from django.db import migrations
 
def add_has_preprinted_template_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='communication_process_status_completed_token').exists():
        ConfigProject.objects.create(
            token='communication_process_status_completed_token',
            name='Procés de comunicació completat',
            value='3'
        )
 
def remove_has_preprinted_template_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='communication_process_status_completed_token').delete()
 
class Migration(migrations.Migration):
 
    dependencies = [
        ('communication', '0019_communication_rejection_reason'),
    ]
 
    operations = [
        migrations.RunPython(add_has_preprinted_template_config, remove_has_preprinted_template_config),
    ]
 