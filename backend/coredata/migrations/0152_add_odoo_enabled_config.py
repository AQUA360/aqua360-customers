from django.db import migrations


def add_odoo_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    if not ConfigProject.objects.filter(token="ODOO_ENABLED").exists():
        ConfigProject.objects.create(
            token="ODOO_ENABLED",
            name="Integració Odoo habilitada",
            value="false",
            file="General",
        )


def remove_odoo_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token="ODOO_ENABLED").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0151_callregister_incident_keep_calls"),
    ]

    operations = [
        migrations.RunPython(add_odoo_enabled_config, remove_odoo_enabled_config),
    ]
