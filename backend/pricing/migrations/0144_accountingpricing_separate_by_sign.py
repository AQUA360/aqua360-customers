from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pricing', '0143_accountingconfig_document_format'),
    ]

    operations = [
        migrations.AddField(
            model_name='accountingpricing',
            name='separate_by_sign',
            field=models.BooleanField(default=False),
        ),
    ]
