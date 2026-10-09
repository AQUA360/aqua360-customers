from django.db import migrations

CONFIG_TOKEN = 'invoice_legacy_concept_order_enabled'


def add_invoice_legacy_concept_order_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token=CONFIG_TOKEN).exists():
        ConfigProject.objects.create(
            token=CONFIG_TOKEN,
            name="Ordena els conceptes de la factura com el sistema anterior (Kais): Quota de Servei primer, i dins de Canon la Fuita abans que la Part Fixa. Nomes te efecte si 'invoice_apply_advanced_grouping' tambe esta a 'true'.",
            value='false',
            file='BILLING'
        )


def remove_invoice_legacy_concept_order_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0128_add_general_billing_summary_preview_config'),
    ]

    operations = [
        migrations.RunPython(add_invoice_legacy_concept_order_config, remove_invoice_legacy_concept_order_config),
    ]
