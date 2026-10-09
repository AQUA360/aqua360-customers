from django.db import migrations

CONFIG_TOKEN = 'general_billing_summary_preview_enabled'


def add_general_billing_summary_preview_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token=CONFIG_TOKEN).exists():
        ConfigProject.objects.create(
            token=CONFIG_TOKEN,
            name="Mostra la previsualitzacio (factures a generar / perdudes / ja revisades) abans de generar el Resum de la facturacio general",
            value='false',
            file='BILLING'
        )


def remove_general_billing_summary_preview_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0127_add_attach_claim_documents_enabled_config'),
    ]

    operations = [
        migrations.RunPython(add_general_billing_summary_preview_config, remove_general_billing_summary_preview_config),
    ]
