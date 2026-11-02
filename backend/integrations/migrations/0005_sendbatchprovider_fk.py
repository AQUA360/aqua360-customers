import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("coredata", "0153_add_send_batch_status_pending_token_config"),
        ("integrations", "0004_sendbatchtype_provider"),
    ]

    operations = [
        migrations.CreateModel(
            name="SendBatchProvider",
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
                ("position", models.IntegerField(blank=True, null=True)),
                ("is_default", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ["position", "token"],
            },
        ),
        migrations.RemoveConstraint(
            model_name="sendbatchtype",
            name="uniq_sendbatchtype_provider_token",
        ),
        migrations.RenameField(
            model_name="sendbatchtype",
            old_name="provider",
            new_name="provider_token",
        ),
        migrations.AddField(
            model_name="sendbatchtype",
            name="provider",
            field=models.ForeignKey(
                help_text="Integració destí del lot (determina client/base URL).",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="batch_types",
                to="integrations.sendbatchprovider",
            ),
        ),
        migrations.AlterField(
            model_name="sendbatchtype",
            name="provider",
            field=models.ForeignKey(
                help_text="Integració destí del lot (determina client/base URL).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="batch_types",
                to="integrations.sendbatchprovider",
            ),
        ),
        migrations.RemoveField(
            model_name="sendbatchtype",
            name="provider_token",
        ),
        migrations.AddConstraint(
            model_name="sendbatchtype",
            constraint=models.UniqueConstraint(
                fields=("provider", "token"),
                name="uniq_sendbatchtype_provider_token",
            ),
        ),
    ]
