from django.db import migrations

CONFIG_TOKEN = 'handle_piggybank_movements_reverse'


def remove_handle_piggybank_movements_reverse_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=CONFIG_TOKEN).delete()


def restore_handle_piggybank_movements_reverse_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    if not ConfigProject.objects.filter(token=CONFIG_TOKEN).exists():
        ConfigProject.objects.create(
            token=CONFIG_TOKEN,
            name=(
                "Inverteix el signe dels moviments de moneder (sense factura ni "
                "compromís) a la declaració comptable"
            ),
            value='false',
            file='BILLING',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0137_add_handle_piggybank_movements_reverse_config'),
    ]

    operations = [
        migrations.RunPython(
            remove_handle_piggybank_movements_reverse_config,
            restore_handle_piggybank_movements_reverse_config,
        ),
    ]
