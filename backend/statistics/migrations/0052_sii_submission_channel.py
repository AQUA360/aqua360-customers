# Generated manually for SII AEAT submission support

from django.db import migrations, models


def set_sii_report_channel(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='sii_report').update(
        submission_channel='sii_emitidas'
    )


def unset_sii_report_channel(apps, schema_editor):
    AvailableReport = apps.get_model('statistics', 'AvailableReport')
    AvailableReport.objects.filter(function_name='sii_report').update(
        submission_channel=None
    )


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0051_add_factdeta_report'),
    ]

    operations = [
        migrations.AddField(
            model_name='availablereport',
            name='submission_channel',
            field=models.CharField(
                blank=True,
                help_text="Si està buit, l'informe no s'envia a cap organisme. Ex.: 'sii_emitidas'.",
                max_length=64,
                null=True,
                verbose_name="Canal d'enviament",
            ),
        ),
        migrations.AddField(
            model_name='dailydocument',
            name='submission_csv',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='dailydocument',
            name='submission_error',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dailydocument',
            name='submission_response',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='dailydocument',
            name='submission_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('pending', 'Pending'),
                    ('correct', 'Correct'),
                    ('partially_correct', 'Partially correct'),
                    ('incorrect', 'Incorrect'),
                    ('error', 'Error'),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='dailydocument',
            name='submitted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(set_sii_report_channel, unset_sii_report_channel),
    ]
