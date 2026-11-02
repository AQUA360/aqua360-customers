from django.db import migrations


def add_send_batch_status_pending_token(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    if not ConfigProject.objects.filter(token="send_batch_status_pending_token").exists():
        ConfigProject.objects.create(
            token="send_batch_status_pending_token",
            name="Token d'estat pendent d'un lot d'enviament (SendBatch)",
            value="0",
            file="General",
        )


def remove_send_batch_status_pending_token(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(token="send_batch_status_pending_token").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0152_add_odoo_enabled_config"),
    ]

    operations = [
        migrations.RunPython(
            add_send_batch_status_pending_token,
            remove_send_batch_status_pending_token,
        ),
    ]
