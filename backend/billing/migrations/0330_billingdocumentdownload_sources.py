import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0329_billingdocumentdownload'),
        ('communication', '0036_messagetemplate_attach_claim_documents'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billingdocumentdownload',
            name='billing',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='document_downloads',
                to='billing.billing',
            ),
        ),
        migrations.AddField(
            model_name='billingdocumentdownload',
            name='communication_process',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='document_downloads',
                to='communication.communicationprocess',
            ),
        ),
        migrations.AddField(
            model_name='billingdocumentdownload',
            name='billings',
            field=models.ManyToManyField(
                blank=True,
                related_name='document_download_sets',
                to='billing.billing',
            ),
        ),
    ]
