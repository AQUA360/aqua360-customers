from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0141_accountingpricing_covers_undeclared'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingconfig',
            name='iva_document_code',
            field=models.CharField(blank=True, default='IR', max_length=2),
        ),
        migrations.AddField(
            model_name='accountingconfig',
            name='iva_series_code',
            field=models.CharField(blank=True, default='02', max_length=2),
        ),
        migrations.AddField(
            model_name='accountingconfig',
            name='iva_operation_code',
            field=models.CharField(blank=True, default='SENSE', max_length=15),
        ),
    ]
