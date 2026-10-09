# Generated manually, following the same pattern as
# pricing/migrations/0102_remove_lineitemtype_name_translations_and_more.py
# (ProductI18n/PriceRateI18n/LineItemTypeI18n)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0117_exploitationsite'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyInvoiceFooterTextI18n',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('ca', 'Català'), ('es', 'Español'), ('gl', 'Galego'), ('en', 'English')], max_length=2)),
                ('invoice_footer_text', models.TextField()),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoice_footer_text_i18n', to='service.company')),
            ],
            options={
                'unique_together': {('company', 'language')},
            },
        ),
        migrations.CreateModel(
            name='CompanyDataProtectionLawTextI18n',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('ca', 'Català'), ('es', 'Español'), ('gl', 'Galego'), ('en', 'English')], max_length=2)),
                ('data_protection_law_text', models.TextField()),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='data_protection_law_text_i18n', to='service.company')),
            ],
            options={
                'unique_together': {('company', 'language')},
            },
        ),
    ]
