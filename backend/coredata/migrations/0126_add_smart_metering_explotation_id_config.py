from django.db import migrations


def add_smart_metering_explotation_id(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.get_or_create(
        token="smart_metering_explotation_id",
        defaults={
            "name": "Smart Metering Exploitation ID (massive readings)",
            "value": None,
        },
    )


def remove_smart_metering_explotation_id(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token="smart_metering_explotation_id").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coredata", "0125_add_aca_notification_enabled_config"),
    ]

    operations = [
        migrations.RunPython(
            add_smart_metering_explotation_id,
            remove_smart_metering_explotation_id,
        ),
    ]
