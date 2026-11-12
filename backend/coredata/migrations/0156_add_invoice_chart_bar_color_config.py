from django.db import migrations


CONFIG_TOKEN = "invoice_chart_bar_color"
CONFIG_NAME = (
    "Color de les barres del gràfic de la factura (hex, p. ex. #e7a225). "
    "Buit: es fan servir els colors de la factura. "
    "Amb valor, les barres usen aquest color i el gràfic no porta fons."
)


def add_invoice_chart_bar_color_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    if not ConfigProject.objects.filter(token=CONFIG_TOKEN).exists():
        ConfigProject.objects.create(
            token=CONFIG_TOKEN,
            name=CONFIG_NAME,
            value="",
            file="BILLING",
        )


def remove_invoice_chart_bar_color_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0155_add_public_org_type_config"),
    ]

    operations = [
        migrations.RunPython(
            add_invoice_chart_bar_color_config,
            remove_invoice_chart_bar_color_config,
        ),
    ]
