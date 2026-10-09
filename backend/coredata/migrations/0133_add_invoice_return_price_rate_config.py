from django.db import migrations


def add_invoice_return_price_rate_config(apps, schema_editor):
    # A les instal·lacions que venen de la llavor de dades aquest ConfigProject
    # ja hi és; a la resta s'havia d'afegir a mà amb SQL. Es crea buit: qui
    # l'omple és marcar la tarifa com a despeses de devolució al formulari.
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.get_or_create(
        token="invoice_return_price_rate_token",
        defaults={
            "name": "Token Price Rate Invoice Return",
            "value": None,
        },
    )


def remove_invoice_return_price_rate_config(apps, schema_editor):
    # No s'esborra: si ja hi era abans d'aquesta migració, esborrar-lo trencaria
    # la identificació de les despeses de devolució.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0132_add_batch_status_billed_token_config"),
    ]

    operations = [
        migrations.RunPython(
            add_invoice_return_price_rate_config,
            remove_invoice_return_price_rate_config,
        ),
    ]
