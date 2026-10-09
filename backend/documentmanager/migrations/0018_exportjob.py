import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

OLD_TABLE = "importexport_exportjob"
OLD_INDEX = "importexpor_request_ae1e28_idx"
NEW_INDEX = "documentman_request_ae1e28_idx"


def create_or_move_table(apps, schema_editor):
    """
    `ExportJob` vivia a `importexport` (migració `importexport.0001_initial`).
    Si la taula ja hi és (BD existent), es reanomena i es conserven les files;
    si no (BD nova o `importexport` no instal·lada), es crea de zero.
    """
    model = apps.get_model("documentmanager", "ExportJob")
    tables = schema_editor.connection.introspection.table_names()
    if OLD_TABLE not in tables:
        schema_editor.create_model(model)
        return

    schema_editor.alter_db_table(model, OLD_TABLE, model._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        constraints = schema_editor.connection.introspection.get_constraints(cursor, model._meta.db_table)
    if OLD_INDEX in constraints:
        schema_editor.execute(
            schema_editor.sql_rename_index % {
                "table": schema_editor.quote_name(model._meta.db_table),
                "old_name": schema_editor.quote_name(OLD_INDEX),
                "new_name": schema_editor.quote_name(NEW_INDEX),
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ('documentmanager', '0017_alter_documentsign_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ExportJob',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('kind', models.CharField(max_length=100)),
                        ('name', models.CharField(max_length=255)),
                        ('params', models.JSONField(blank=True, default=dict)),
                        ('task_id', models.CharField(blank=True, max_length=255, null=True, unique=True)),
                        ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=20)),
                        ('error_message', models.TextField(blank=True, null=True)),
                        ('file_url', models.TextField(blank=True, null=True)),
                        ('file_name', models.CharField(blank=True, max_length=255, null=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('started_at', models.DateTimeField(blank=True, null=True)),
                        ('completed_at', models.DateTimeField(blank=True, null=True)),
                        ('dismissed_at', models.DateTimeField(blank=True, null=True)),
                        ('document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='documentmanager.document')),
                        ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='export_jobs', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'ordering': ['-created_at'],
                        'indexes': [models.Index(fields=['requested_by', '-created_at'], name='documentman_request_ae1e28_idx')],
                    },
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(create_or_move_table, migrations.RunPython.noop),
    ]
