# Generated manually for DailyDocumentTemplate monthly periodicity

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0063_billingconsumption_chart'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dailydocumenttemplate',
            name='periodicity',
            field=models.CharField(
                choices=[
                    ('daily', 'Daily'),
                    ('weekly', 'Weekly (day of week)'),
                    ('monthly', 'Monthly (day of month)'),
                    ('every_x_days', 'Every X days'),
                ],
                default='daily',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='dailydocumenttemplate',
            name='month_day',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
