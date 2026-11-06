import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("integrations", "0002_odoo_bulk"),
    ]

    operations = [
        migrations.CreateModel(
            name="SendBatchObservation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, null=True, blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True, null=True, blank=True)),
                ("observation", models.TextField(blank=True, null=True)),
                ("status_name", models.CharField(blank=True, max_length=255, null=True)),
                ("is_important", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "send_batch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="observations",
                        to="integrations.sendbatch",
                    ),
                ),
                (
                    "status",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="integrations.sendbatchstatus",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
