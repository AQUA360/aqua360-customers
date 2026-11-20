from django.db import migrations, models

WARNING_TOKEN = 'terminated_contract'
NEW_DESCRIPTION = (
    "El contracte està de baixa i l'usuari l'ha triat per facturar en confirmar la facturació."
)
OLD_DESCRIPTION = (
    "El contracte està de baixa: la factura s'ha exclòs de la facturació. "
    "Torneu-la a incloure només si s'ha de facturar."
)


def update_warning_description(apps, schema_editor):
    InvoiceWarning = apps.get_model('billing', 'InvoiceWarning')
    InvoiceWarning.objects.filter(token=WARNING_TOKEN, description=OLD_DESCRIPTION).update(
        description=NEW_DESCRIPTION,
    )


def restore_warning_description(apps, schema_editor):
    InvoiceWarning = apps.get_model('billing', 'InvoiceWarning')
    InvoiceWarning.objects.filter(token=WARNING_TOKEN, description=NEW_DESCRIPTION).update(
        description=OLD_DESCRIPTION,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0350_add_terminated_contract_warning'),
    ]

    operations = [
        migrations.AddField(
            model_name='billing',
            name='terminated_contract_ids_to_bill',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(update_warning_description, restore_warning_description),
    ]
