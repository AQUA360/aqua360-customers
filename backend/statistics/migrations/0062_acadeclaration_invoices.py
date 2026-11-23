from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0335_invoice_pdf_page_count'),
        ('statistics', '0061_dailydocumenttemplate_periodicity'),
    ]

    operations = [
        migrations.AddField(
            model_name='acadeclaration',
            name='invoices',
            field=models.ManyToManyField(blank=True, related_name='aca_declarations', to='billing.invoice'),
        ),
    ]
