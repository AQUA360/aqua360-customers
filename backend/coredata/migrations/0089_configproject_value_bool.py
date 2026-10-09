from django.db import migrations

def add_has_preprinted_template_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='has_preprinted_template').exists():
        ConfigProject.objects.create(
            token='has_preprinted_template',
            name='Explotació amb plantilla impresa',
            value='false',
            file='Billing'
        )

def remove_has_preprinted_template_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='has_preprinted_template').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0088_add_ov_enabled_config'),
    ]

    operations = [
        migrations.RunPython(add_has_preprinted_template_config, remove_has_preprinted_template_config),
    ]
