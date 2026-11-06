from django.db import migrations


STATUSES = (
    (
        "send_batch_status_pending_token",
        "Token d'estat pendent d'un lot d'enviament (SendBatch)",
        "0",
    ),
    (
        "send_batch_status_processing_token",
        "Token d'estat en procés d'un lot d'enviament (SendBatch)",
        "1",
    ),
    (
        "send_batch_status_finalized_token",
        "Token d'estat finalitzat d'un lot d'enviament (SendBatch)",
        "2",
    ),
)


def add_send_batch_status_lifecycle_tokens(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    for token, name, value in STATUSES:
        existing = ConfigProject.objects.filter(token=token).first()
        if existing:
            # Pending ja existia amb value "0"; assegurem el valor esperat.
            if existing.value != value:
                existing.value = value
                existing.save(update_fields=["value"])
            continue
        ConfigProject.objects.create(
            token=token,
            name=name,
            value=value,
            file="General",
        )


def remove_send_batch_status_lifecycle_tokens(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(
        token__in=[
            "send_batch_status_processing_token",
            "send_batch_status_finalized_token",
        ]
    ).delete()
    # No esborrem pending: el va crear 0153.


class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0153_add_send_batch_status_pending_token_config"),
    ]

    operations = [
        migrations.RunPython(
            add_send_batch_status_lifecycle_tokens,
            remove_send_batch_status_lifecycle_tokens,
        ),
    ]
