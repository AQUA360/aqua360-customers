import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0328_reading_document_smart_metering_scope'),
        ('documentmanager', '0018_exportjob'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BillingDocumentDownload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_type_tokens', models.JSONField(blank=True, default=list)),
                ('delivery', models.CharField(choices=[('all', 'All'), ('postal', 'Postal'), ('email', 'Email')], default='all', max_length=20)),
                ('ordering', models.CharField(choices=[('contact_address', 'Contact address'), ('contract_token', 'Contract code'), ('invoice_code', 'Invoice code')], default='contact_address', max_length=40)),
                ('descending', models.BooleanField(default=False)),
                ('invoice_count', models.IntegerField(default=0)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('task_id', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('billing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_downloads', to='billing.billing')),
                ('document', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='documentmanager.document')),
                ('requested_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='billing_document_downloads', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['billing', '-created_at'], name='billing_docdownload_bill_idx')],
            },
        ),
    ]
