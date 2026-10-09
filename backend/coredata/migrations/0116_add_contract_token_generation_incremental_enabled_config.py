from django.db import migrations

def add_contract_token_generation_incremental_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED').exists():
        ConfigProject.objects.create(
            token='CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED',
            name='Generació incremental del codi de contracte (en lloc de basada en data)',
            value='false',
            file='General'
        )

def remove_contract_token_generation_incremental_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0115_add_canvi_nom_contract_request_type_config'),
    ]

    operations = [
        migrations.RunPython(add_contract_token_generation_incremental_enabled_config, remove_contract_token_generation_incremental_enabled_config),
    ]
