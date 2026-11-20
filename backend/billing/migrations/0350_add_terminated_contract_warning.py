from django.db import migrations

WARNING_TOKEN = 'terminated_contract'
CONFIG_TOKEN = 'invoice_warning_terminated_contract'


def add_terminated_contract_warning(apps, schema_editor):
    InvoiceWarning = apps.get_model('billing', 'InvoiceWarning')
    ConfigProject = apps.get_model('coredata', 'ConfigProject')

    InvoiceWarning.objects.get_or_create(
        token=WARNING_TOKEN,
        defaults={
            'name': 'Contracte de baixa',
            'color': '#ef4444',
            'description': (
                "El contracte està de baixa: la factura s'ha exclòs de la facturació. "
                "Torneu-la a incloure només si s'ha de facturar."
            ),
            'is_default': False,
            'position': 8,
        },
    )

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence('coredata_configproject', 'id'), "
            "(SELECT MAX(id) FROM coredata_configproject));"
        )

    ConfigProject.objects.update_or_create(
        token=CONFIG_TOKEN,
        defaults={
            'name': "Token de l'avís de factura de contracte de baixa",
            'value': WARNING_TOKEN,
        },
    )


def remove_terminated_contract_warning(apps, schema_editor):
    InvoiceWarning = apps.get_model('billing', 'InvoiceWarning')
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    InvoiceWarning.objects.filter(token=WARNING_TOKEN).delete()
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0349_invoice_person_token_indexes'),
        ('coredata', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_terminated_contract_warning, remove_terminated_contract_warning),
    ]
