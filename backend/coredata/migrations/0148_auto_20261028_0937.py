from django.db import migrations

CONFIG_TOKEN = 'use_exploitation_token_for_payment'
CONFIG_NAME = "Utilitzar el token de l'explotació per a la facturació"
DEFAULT_VALUE = 'false'


def add_use_exploitation_token_for_payment_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token=CONFIG_TOKEN,
        defaults={'name': CONFIG_NAME, 'value': DEFAULT_VALUE},
    )


def remove_use_exploitation_token_for_payment_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0144_merge_20261023_0800'),
    ]

    operations = [
        migrations.RunPython(
            add_use_exploitation_token_for_payment_config,
            remove_use_exploitation_token_for_payment_config,
        ),
    ]
