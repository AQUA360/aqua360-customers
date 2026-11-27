from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0142_accountingconfig_iva_document_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingconfig',
            name='document_format',
            field=models.CharField(
                choices=[('xml', 'XML'), ('csv', 'CSV')],
                default='xml',
                max_length=10,
            ),
        ),
    ]
