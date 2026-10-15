from django.db import migrations

CONFIGS = [
    {
        "token": "order_reason_contract_activation",
        "name": "Motiu ordre Alta de contracte",
        "value": "contract_activation",
    },
    {
        "token": "order_reason_new_connection_request",
        "name": "Motiu ordre Nova sol·licitud d'escomesa",
        "value": "new_connection_request",
    },
    {
        "token": "order_reason_customer_supply_cut",
        "name": "Motiu ordre Tall de subministrament",
        "value": "customer_supply_cut_request",
    },
]


def add_order_reason_configs(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")

    for config in CONFIGS:
        obj, created = ConfigProject.objects.get_or_create(
            token=config["token"],
            defaults={"name": config["name"], "value": config["value"]},
        )
        if not created and not obj.value:
            obj.value = config["value"]
            obj.save()


def remove_order_reason_configs(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token__in=[c["token"] for c in CONFIGS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0138_add_contract_termination_order_reason_config"),
    ]

    operations = [
        migrations.RunPython(
            add_order_reason_configs,
            remove_order_reason_configs,
        ),
    ]
