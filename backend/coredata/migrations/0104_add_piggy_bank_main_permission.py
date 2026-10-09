from django.db import migrations

def add_main_permission(apps, schema_editor):
    MainPermission = apps.get_model('coredata', 'MainPermission')
    MainPermission.objects.get_or_create(
        name='piggy_bank',
        defaults={
            'view_key': 'view_piggy_bank',
            'change_key': 'change_piggy_bank',
            'affected_models': 'contract.piggybank,coredata.personpiggybank',
            'is_default': False
        }
    )

def remove_main_permission(apps, schema_editor):
    MainPermission = apps.get_model('coredata', 'MainPermission')
    MainPermission.objects.filter(name='piggy_bank').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0103_add_fire_connection_use_type_config'),
    ]

    operations = [
        migrations.RunPython(add_main_permission, remove_main_permission),
    ]
