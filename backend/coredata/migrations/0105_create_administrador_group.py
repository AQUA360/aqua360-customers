from django.db import migrations

def create_admin_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Administrador')

def remove_admin_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='Administrador').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0104_add_piggy_bank_main_permission'),
    ]

    operations = [
        migrations.RunPython(create_admin_group, remove_admin_group),
    ]
