from django.db import migrations

CONFIG_TOKEN = 'use_manual_bank_remittance'


def add_use_manual_bank_remittance_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token=CONFIG_TOKEN).exists():
        ConfigProject.objects.create(
            token=CONFIG_TOKEN,
            name="Remeses SEPA amb selector de banc manual (sense encaminament automatic per entitat del pagador)",
            value='false',
            file='BILLING'
        )


def remove_use_manual_bank_remittance_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0134_person_dni_validated'),
    ]

    operations = [
        migrations.RunPython(add_use_manual_bank_remittance_config, remove_use_manual_bank_remittance_config),
    ]
