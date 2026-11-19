from django.db import migrations

WARNING_TOKEN = 'pending_termination'
CONFIG_TOKEN = 'invoice_warning_pending_termination'


def add_pending_termination_warning(apps, schema_editor):
    InvoiceWarning = apps.get_model('billing', 'InvoiceWarning')
    ConfigProject = apps.get_model('coredata', 'ConfigProject')

    InvoiceWarning.objects.get_or_create(
        token=WARNING_TOKEN,
        defaults={
            'name': 'Contracte amb baixa pendent',
            'color': '#ef4444',
            'description': (
                "El contracte té una baixa iniciada i no finalitzada (p. ex. un canvi de titular): "
                "reviseu si la factura ha d'anar a la nova alta."
            ),
            'is_default': False,
            'position': 7,
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
            'name': "Token de l'avís de factura de contracte amb baixa pendent",
            'value': WARNING_TOKEN,
        },
    )


def remove_pending_termination_warning(apps, schema_editor):
    InvoiceWarning = apps.get_model('billing', 'InvoiceWarning')
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    InvoiceWarning.objects.filter(token=WARNING_TOKEN).delete()
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0347_biller_split_by_company'),
        ('coredata', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_pending_termination_warning, remove_pending_termination_warning),
    ]
