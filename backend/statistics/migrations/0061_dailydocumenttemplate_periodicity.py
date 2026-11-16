# Generated manually for DailyDocumentTemplate periodicity + DailyDocument period range

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0060_merge_20261116_0953'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailydocumenttemplate',
            name='periodicity',
            field=models.CharField(
                choices=[
                    ('daily', 'Daily'),
                    ('weekly', 'Weekly (day of week)'),
                    ('every_x_days', 'Every X days'),
                ],
                default='daily',
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name='dailydocumenttemplate',
            name='weekday',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dailydocumenttemplate',
            name='interval_days',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dailydocumenttemplate',
            name='period_anchor_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dailydocument',
            name='period_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dailydocument',
            name='period_end_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
