from django.db import migrations


TOKEN = 'billing_pdf_parallel_workers'


def create_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token=TOKEN,
        defaults={
            'name': "Facturació: PDF de les factures que es generen alhora (1 = un darrere l'altre; "
                    "com a màxim, els processos del worker menys un)",
            'value': '4',
            'file': 'Billing',
        },
    )


def delete_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0349_invoice_person_token_indexes'),
        ('coredata', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_config, delete_config),
    ]
