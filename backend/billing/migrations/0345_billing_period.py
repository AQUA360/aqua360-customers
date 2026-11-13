from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0344_block_remittance_if_unpaid_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='billing',
            name='period_start',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='billing',
            name='period_end',
            field=models.DateField(blank=True, null=True),
        ),
    ]
