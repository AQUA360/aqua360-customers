from django.db import migrations


def add_allow_contract_date_edit_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.get_or_create(
        token="allow_contract_date_edit",
        defaults={
            "name": "Permet editar la data del contracte",
            "value": "false",
        },
    )


def remove_allow_contract_date_edit_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token="allow_contract_date_edit").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0109_personrecord_year"),
    ]

    operations = [
        migrations.RunPython(
            add_allow_contract_date_edit_config,
            remove_allow_contract_date_edit_config,
        ),
    ]
