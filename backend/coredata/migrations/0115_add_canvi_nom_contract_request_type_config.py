from django.db import migrations


CONFIG_TOKEN = "contract_request_type_change_name_token"
REQUEST_TYPE_TOKEN = "canvi_nom"


def create_config(apps, schema_editor):
    ContractRequestType = apps.get_model("contract", "ContractRequestType")
    ConfigProject = apps.get_model("coredata", "ConfigProject")

    request_type, _ = ContractRequestType.objects.get_or_create(
        token=REQUEST_TYPE_TOKEN,
        defaults={
            "name": "Canvi de nom",
            "has_persons": False,
            "is_active": True,
            "is_default": False,
        },
    )

    ConfigProject.objects.update_or_create(
        token=CONFIG_TOKEN,
        defaults={
            "name": "Contract request type: canvi de nom",
            "value": str(request_type.id),
        },
    )


def remove_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0114_update_contract_keeper_use_type_name"),
        ("contract", "0227_contractrequest_meter_mode"),
    ]

    operations = [
        migrations.RunPython(create_config, remove_config),
    ]
