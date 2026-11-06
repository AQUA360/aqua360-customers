# Generated manually for DailyDocumentTemplate notify_users / notify_groups

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('statistics', '0053_merge_20261105_1241'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailydocumenttemplate',
            name='notify_groups',
            field=models.ManyToManyField(
                blank=True,
                related_name='daily_document_templates_to_notify',
                to='auth.group',
            ),
        ),
        migrations.AddField(
            model_name='dailydocumenttemplate',
            name='notify_users',
            field=models.ManyToManyField(
                blank=True,
                related_name='daily_document_templates_to_notify',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
