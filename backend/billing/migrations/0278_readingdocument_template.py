from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('statistics', '0023_readingbatchimporttemplate_readingbatchimportcolumn'),
        ('billing', '0277_revert_invoice_status_class_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='readingdocument',
            name='template',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reading_documents',
                to='statistics.readingbatchimporttemplate',
            ),
        ),
    ]
