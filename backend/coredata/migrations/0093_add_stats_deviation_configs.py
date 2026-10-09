from django.db import migrations

def add_stats_configs(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    
    # stats_consumption_threshold
    if not ConfigProject.objects.filter(token='stats_consumption_threshold').exists():
        ConfigProject.objects.create(
            token='stats_consumption_threshold',
            name='Llindar de desviació de consum per a estadístiques (%)',
            value='50',
            file='Statistics'
        )
        
    # stats_days_threshold
    if not ConfigProject.objects.filter(token='stats_days_threshold').exists():
        ConfigProject.objects.create(
            token='stats_days_threshold',
            name='Llindar de desviació de dies per a estadístiques (%)',
            value='50',
            file='Statistics'
        )

def remove_stats_configs(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token__in=['stats_consumption_threshold', 'stats_days_threshold']).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0092_alter_personaddress_attention_to'),
    ]

    operations = [
        migrations.RunPython(add_stats_configs, remove_stats_configs),
    ]
