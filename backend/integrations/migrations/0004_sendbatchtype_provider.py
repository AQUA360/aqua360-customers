from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0003_sendbatchobservation"),
    ]

    operations = [
        migrations.AddField(
            model_name="sendbatchtype",
            name="provider",
            field=models.CharField(
                choices=[("odoo", "Odoo")],
                db_index=True,
                default="odoo",
                help_text="Integració destí del lot (determina client/base URL).",
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="sendbatchtype",
            name="endpoint",
            field=models.CharField(
                help_text="Ruta relativa del proveïdor, p.ex. /batch/invoices",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="sendbatchtype",
            name="is_default",
            field=models.BooleanField(
                default=False,
                help_text="Tipus per defecte dins d'aquest provider (p.ex. invoices Odoo).",
            ),
        ),
        migrations.AlterField(
            model_name="sendbatchtype",
            name="token",
            field=models.CharField(max_length=64),
        ),
        migrations.AddConstraint(
            model_name="sendbatchtype",
            constraint=models.UniqueConstraint(
                fields=("provider", "token"),
                name="uniq_sendbatchtype_provider_token",
            ),
        ),
        migrations.AlterModelOptions(
            name="sendbatchtype",
            options={"ordering": ["provider", "position", "token"]},
        ),
    ]
