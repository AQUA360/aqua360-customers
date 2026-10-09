from django.db import migrations


def add_reference_suffix_barcode_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.update_or_create(
        token="reference_suffix_barcode_token",
        defaults={
            "name": "Sufix referencia codi de barres",
            "value": "501",
            "file": "Billing",
        },
    )


def remove_reference_suffix_barcode_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token="reference_suffix_barcode_token").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coredata", "0089_configproject_value_bool"),
    ]

    operations = [
        migrations.RunPython(
            add_reference_suffix_barcode_config,
            remove_reference_suffix_barcode_config,
        ),
    ]

