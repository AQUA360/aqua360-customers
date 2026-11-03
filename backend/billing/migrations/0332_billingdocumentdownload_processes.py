from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0036_messagetemplate_attach_claim_documents'),
        ('billing', '0331_billingdocumentdownload_batches'),
    ]

    operations = [
        migrations.AddField(
            model_name='billingdocumentdownload',
            name='communication_processes',
            field=models.ManyToManyField(
                blank=True,
                related_name='document_download_sets',
                to='communication.communicationprocess',
            ),
        ),
    ]
