from django.db import migrations, models
from django.db.models import Q


def mark_existing_documents_processed(apps, schema_editor):
    ReadingDocument = apps.get_model('billing', 'ReadingDocument')
    ReadingDocument.objects.filter(
        Q(readings__isnull=False) | Q(not_found_readings__isnull=False)
    ).distinct().update(status='processed')


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0300_alter_billingqueue_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='readingdocument',
            name='last_preview',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='readingdocument',
            name='processed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='readingdocument',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('processed', 'Processed'),
                    ('failed', 'Failed'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='readingdocument',
            name='task_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(mark_existing_documents_processed, migrations.RunPython.noop),
    ]
