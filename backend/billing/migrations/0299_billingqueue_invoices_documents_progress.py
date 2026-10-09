from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0298_readingdocumentnotfound'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingqueue',
            name='invoices_processed',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='billingqueue',
            name='documents_generated',
            field=models.IntegerField(default=0),
        ),
    ]
