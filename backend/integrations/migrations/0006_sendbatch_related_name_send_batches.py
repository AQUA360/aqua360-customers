from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0005_sendbatchprovider_fk"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sendbatch",
            name="billing",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="send_batches",
                to="billing.billing",
            ),
        ),
        migrations.AlterField(
            model_name="sendbatch",
            name="commitment_deposits",
            field=models.ManyToManyField(
                blank=True,
                related_name="send_batches",
                to="billing.commitmentdeposit",
            ),
        ),
        migrations.AlterField(
            model_name="sendbatch",
            name="invoices",
            field=models.ManyToManyField(
                blank=True,
                related_name="send_batches",
                to="billing.invoice",
            ),
        ),
        migrations.AlterField(
            model_name="sendbatch",
            name="payments",
            field=models.ManyToManyField(
                blank=True,
                help_text="PaymentMovements enviats com a pagaments/cobraments.",
                related_name="send_batches",
                to="billing.paymentmovement",
            ),
        ),
    ]
