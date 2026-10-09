from django.db import migrations

def add_document_sign_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token='DOCUMENT_SIGN_ENABLED').exists():
        ConfigProject.objects.create(
            token='DOCUMENT_SIGN_ENABLED',
            name='Signatura de documents (OTP) habilitada',
            value='false',
            file='General'
        )

def remove_document_sign_enabled_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='DOCUMENT_SIGN_ENABLED').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0112_add_smart_metering_authentication_token'),
    ]

    operations = [
        migrations.RunPython(add_document_sign_enabled_config, remove_document_sign_enabled_config),
    ]
