from django.db import migrations

CONFIG_TOKEN = 'contract_housing_units_variable_type_token'
CONFIG_NAME = "Token del VariableType que indica el nombre d'habitatges del contracte (es mostra al detall del contracte)"
DEFAULT_VALUE = 'general'


def add_contract_housing_units_variable_type_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token=CONFIG_TOKEN,
        defaults={'name': CONFIG_NAME, 'value': DEFAULT_VALUE},
    )


def remove_contract_housing_units_variable_type_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0144_merge_20261023_0800'),
    ]

    operations = [
        migrations.RunPython(
            add_contract_housing_units_variable_type_config,
            remove_contract_housing_units_variable_type_config,
        ),
    ]
