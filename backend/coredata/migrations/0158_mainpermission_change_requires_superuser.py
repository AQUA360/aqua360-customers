from django.db import migrations, models


def mark_users_permission(apps, schema_editor):
    MainPermission = apps.get_model('coredata', 'MainPermission')
    MainPermission.objects.filter(name='users').update(change_requires_superuser=True)


def unmark_users_permission(apps, schema_editor):
    MainPermission = apps.get_model('coredata', 'MainPermission')
    MainPermission.objects.filter(name='users').update(change_requires_superuser=False)


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0157_deploy_record'),
    ]

    operations = [
        migrations.AddField(
            model_name='mainpermission',
            name='change_requires_superuser',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_users_permission, unmark_users_permission),
    ]
