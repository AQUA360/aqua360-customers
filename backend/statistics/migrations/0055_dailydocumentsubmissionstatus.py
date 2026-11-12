# Generated manually: configurable DailyDocumentSubmissionStatus + FK migration

from django.db import migrations, models
import django.db.models.deletion


DEFAULT_SUBMISSION_STATUSES = (
    # token, name_es, name_ca, color, position, is_error
    ('pending', 'Pendiente', 'Pendent', 'slate', 0, False),
    ('correct', 'Correcto', 'Correcte', 'green', 1, False),
    ('partially_correct', 'Parcialmente correcto', 'Parcialment correcte', 'orange', 2, True),
    ('incorrect', 'Incorrecto', 'Incorrecte', 'red', 3, True),
    ('error', 'Error', 'Error', 'red', 4, True),
)


def _language_is_es(apps):
    try:
        from django.conf import settings
        language = getattr(settings, 'LANGUAGE', None) or getattr(settings, 'LANGUAGE_CODE', None) or 'ca'
        language = str(language).lower().replace('_', '-')
        return language == 'es' or language.startswith('es-')
    except Exception:
        return False


def seed_submission_statuses(apps, schema_editor):
    DailyDocumentSubmissionStatus = apps.get_model('statistics', 'DailyDocumentSubmissionStatus')
    use_es = _language_is_es(apps)
    for token, name_es, name_ca, color, position, is_error in DEFAULT_SUBMISSION_STATUSES:
        DailyDocumentSubmissionStatus.objects.update_or_create(
            token=token,
            defaults={
                'name': name_es if use_es else name_ca,
                'color': color,
                'position': position,
                'is_error': is_error,
                'is_active': True,
            },
        )


def migrate_submission_status_values(apps, schema_editor):
    DailyDocument = apps.get_model('statistics', 'DailyDocument')
    DailyDocumentSubmissionStatus = apps.get_model('statistics', 'DailyDocumentSubmissionStatus')
    by_token = {
        row.token: row
        for row in DailyDocumentSubmissionStatus.objects.all()
        if row.token
    }
    for doc in DailyDocument.objects.exclude(submission_status_legacy__isnull=True).exclude(submission_status_legacy=''):
        status = by_token.get(doc.submission_status_legacy) or by_token.get('error')
        if status is not None:
            doc.submission_status = status
            doc.save(update_fields=['submission_status'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0054_dailydocumenttemplate_notify_targets'),
    ]

    operations = [
        migrations.CreateModel(
            name='DailyDocumentSubmissionStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True, blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True, blank=True)),
                ('token', models.CharField(blank=True, max_length=255, null=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('color', models.CharField(blank=True, max_length=255, null=True)),
                ('position', models.IntegerField(blank=True, null=True)),
                ('is_error', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Daily Document Submission Status',
                'verbose_name_plural': 'Daily Document Submission Statuses',
                'ordering': ['position', 'id'],
            },
        ),
        migrations.RunPython(seed_submission_statuses, noop_reverse),
        migrations.RenameField(
            model_name='dailydocument',
            old_name='submission_status',
            new_name='submission_status_legacy',
        ),
        migrations.AddField(
            model_name='dailydocument',
            name='submission_status',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='daily_documents',
                to='statistics.dailydocumentsubmissionstatus',
            ),
        ),
        migrations.RunPython(migrate_submission_status_values, noop_reverse),
        migrations.RemoveField(
            model_name='dailydocument',
            name='submission_status_legacy',
        ),
    ]
