from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0330_billingdocumentdownload_sources'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingdocumentdownload',
            name='batch_mode',
            field=models.CharField(
                choices=[('none', 'Single PDF'), ('count', 'By document count'), ('size', 'By megabytes')],
                default='none',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='billingdocumentdownload',
            name='batch_size',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='billingdocumentdownload',
            name='batch_count',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
