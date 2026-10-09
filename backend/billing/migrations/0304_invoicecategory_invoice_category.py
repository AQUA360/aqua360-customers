import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0303_paymentremittance_is_return'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('token', models.CharField(blank=True, max_length=255, null=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('position', models.IntegerField(blank=True, null=True)),
                ('is_default', models.BooleanField(default=False)),
            ],
        ),
        migrations.AddField(
            model_name='invoice',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices', to='billing.invoicecategory'),
        ),
    ]
