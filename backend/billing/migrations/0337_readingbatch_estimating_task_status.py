from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('billing', '0336_invoice_list_order_idx')]

    operations = [
        migrations.AddField(
            model_name='readingbatch',
            name='estimating_task_status',
            field=models.CharField(max_length=16, null=True, blank=True),
        ),
    ]
