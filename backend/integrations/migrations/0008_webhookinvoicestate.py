from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0007_webhookevent'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebhookInvoiceState',
            fields=[
                ('invoice_id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('status_id', models.BigIntegerField(blank=True, null=True)),
                ('is_returned', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
