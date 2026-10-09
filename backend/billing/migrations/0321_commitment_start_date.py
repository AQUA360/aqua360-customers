from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0320_joinedpayment_claim_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='commitmentdeposit',
            name='start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='paymentcommitment',
            name='start_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
