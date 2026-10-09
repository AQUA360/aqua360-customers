from django.db import migrations


def add_use_multiple_companies_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.get_or_create(
        token="use_multiple_companies",
        defaults={
            "name": "Use multiple companies",
            "value": "false",
        },
    )


def remove_use_multiple_companies_config(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token="use_multiple_companies").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0099_add_incident_closed_status_config"),
    ]

    operations = [
        migrations.RunPython(
            add_use_multiple_companies_config,
            remove_use_multiple_companies_config,
        ),
    ]
