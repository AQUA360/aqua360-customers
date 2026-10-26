from django.db import migrations

def add_attach_extra_docs_in_claims_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='attach_extra_docs_in_claims').exists():
        ConfigProject.objects.create(
            token='attach_extra_docs_in_claims',
            name="Adjuntar factures i rebuts (o document agrupat) a les comunicacions d'impagats",
            value='true',
            file='COMMUNICATION'
        )

def remove_attach_extra_docs_in_claims_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='attach_extra_docs_in_claims').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0142_merge_20261021_1259'),
    ]

    operations = [
        migrations.RunPython(add_attach_extra_docs_in_claims_config, remove_attach_extra_docs_in_claims_config),
    ]
