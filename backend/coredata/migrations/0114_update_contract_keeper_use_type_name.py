from django.db import migrations


def update_name(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(
        token='contract_keeper_use_type_token'
    ).update(name='Token Contracte Ús Agrícola')


def revert_name(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(
        token='contract_keeper_use_type_token'
    ).update(name='Token Contract Keeper Use Type')


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0113_add_document_sign_enabled_config'),
    ]

    operations = [
        migrations.RunPython(update_name, revert_name),
    ]
