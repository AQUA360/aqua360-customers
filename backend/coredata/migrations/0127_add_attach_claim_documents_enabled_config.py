from django.db import migrations

def add_attach_claim_documents_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='ATTACH_CLAIM_DOCUMENTS_ENABLED').exists():
        ConfigProject.objects.create(
            token='ATTACH_CLAIM_DOCUMENTS_ENABLED',
            name="Adjunta per defecte el document de reclamació al correu electrònic",
            value='true',
            file='COMMUNICATION'
        )

def remove_attach_claim_documents_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='ATTACH_CLAIM_DOCUMENTS_ENABLED').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0126_add_smart_metering_explotation_id_config'),
    ]

    operations = [
        migrations.RunPython(add_attach_claim_documents_enabled_config, remove_attach_claim_documents_enabled_config),
    ]
