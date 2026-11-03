import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0332_billingdocumentdownload_processes"),
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SendBatchType",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("token", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                (
                    "endpoint",
                    models.CharField(
                        help_text="Ruta relativa Odoo del lot, p.ex. /batch/invoices",
                        max_length=255,
                    ),
                ),
                ("position", models.IntegerField(blank=True, null=True)),
                ("is_default", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="SendBatchStatus",
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
                ("token", models.CharField(blank=True, max_length=255, null=True)),
                ("name", models.CharField(blank=True, max_length=255, null=True)),
                ("color", models.CharField(blank=True, max_length=255, null=True)),
                ("position", models.IntegerField(blank=True, null=True)),
                ("is_default", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="SendBatch",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "token",
                    models.CharField(
                        help_text="batch_id enviat a Odoo (1-64: [A-Za-z0-9._-]).",
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("instant_status_code", models.IntegerField(blank=True, null=True)),
                ("instant_response", models.JSONField(blank=True, null=True)),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("summary", models.JSONField(blank=True, null=True)),
                ("final_response", models.JSONField(blank=True, null=True)),
                (
                    "batch_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="batches",
                        to="integrations.sendbatchtype",
                    ),
                ),
                (
                    "billing",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="odoo_batches",
                        to="billing.billing",
                    ),
                ),
                (
                    "commitment_deposits",
                    models.ManyToManyField(
                        blank=True,
                        related_name="odoo_batches",
                        to="billing.commitmentdeposit",
                    ),
                ),
                (
                    "invoices",
                    models.ManyToManyField(
                        blank=True,
                        related_name="odoo_batches",
                        to="billing.invoice",
                    ),
                ),
                (
                    "payments",
                    models.ManyToManyField(
                        blank=True,
                        help_text="PaymentMovements enviats com a pagaments/cobraments.",
                        related_name="odoo_batches",
                        to="billing.paymentmovement",
                    ),
                ),
                (
                    "related_batch",
                    models.ForeignKey(
                        blank=True,
                        help_text="Lot original quan aquest és un reenviament d'errors.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="resend_batches",
                        to="integrations.sendbatch",
                    ),
                ),
                (
                    "status",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="batches",
                        to="integrations.sendbatchstatus",
                    ),
                ),
            ],
            options={
                "verbose_name": "Send batch",
                "verbose_name_plural": "Send batches",
                "ordering": ["-created_at"],
            },
        ),
    ]
