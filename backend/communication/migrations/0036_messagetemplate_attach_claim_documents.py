from django.db import migrations, models


CONFIG_TOKEN = 'ATTACH_CLAIM_DOCUMENTS_ENABLED'


def move_config_to_templates(apps, schema_editor):
    """El valor del configProject passa a ser el de totes les plantilles existents."""
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    MessageTemplate = apps.get_model('communication', 'MessageTemplate')
    config = ConfigProject.objects.filter(token=CONFIG_TOKEN).first()
    if config and str(config.value).strip().lower() == 'false':
        MessageTemplate.objects.update(attach_claim_documents=False)
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


def restore_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    MessageTemplate = apps.get_model('communication', 'MessageTemplate')
    if ConfigProject.objects.filter(token=CONFIG_TOKEN).exists():
        return
    any_disabled = MessageTemplate.objects.filter(attach_claim_documents=False).exists()
    ConfigProject.objects.create(
        token=CONFIG_TOKEN,
        name="Adjunta per defecte el document de reclamació al correu electrònic",
        value='false' if any_disabled else 'true',
        file='COMMUNICATION',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0035_communication_sms_sent_at'),
        ('coredata', '0127_add_attach_claim_documents_enabled_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagetemplate',
            name='attach_claim_documents',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(move_config_to_templates, restore_config),
    ]
