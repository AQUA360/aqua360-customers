from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0138_accountingpricing_counterpart_accounting_pricing'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingadditionalline',
            name='declared_as_return',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='accountingpricing',
            name='declared_as_return',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
