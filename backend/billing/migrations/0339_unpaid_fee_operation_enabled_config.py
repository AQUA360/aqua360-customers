from django.db import migrations


TOKEN = 'unpaid_fee_operation_enabled'


def create_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token=TOKEN,
        defaults={
            'name': "Mostrar l'operació «Despeses d'impagat» a la llista de factures",
            'value': 'false',
        },
    )


def delete_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0338_merge_20261106_1229'),
    ]

    operations = [
        migrations.RunPython(create_config, delete_config),
    ]
