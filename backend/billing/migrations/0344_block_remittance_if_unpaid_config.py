from django.db import migrations


TOKEN = 'block_remittance_if_unpaid'


def create_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token=TOKEN,
        defaults={
            'name': "Procés de facturació: si el contracte té factures pendents de cobrar, "
                    "les factures noves passen de domiciliació a Pagament bancari",
            'value': 'false',
        },
    )


def delete_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0343_billing_process_errors'),
    ]

    operations = [
        migrations.RunPython(create_config, delete_config),
    ]
