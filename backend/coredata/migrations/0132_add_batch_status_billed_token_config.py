from django.db import migrations


def add_batch_status_billed_token(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.get_or_create(
        token="batch_status_billed_token",
        defaults={
            "name": "Token de estat facturat d'un lot de lectura",
            "value": "3",
            "file": None,
        },
    )


def remove_batch_status_billed_token(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token="batch_status_billed_token").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0131_personlog"),
    ]

    operations = [
        migrations.RunPython(
            add_batch_status_billed_token,
            remove_batch_status_billed_token,
        ),
    ]
