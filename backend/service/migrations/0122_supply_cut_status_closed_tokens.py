from django.db import migrations


def create_closed_tokens_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token='supply_cut_status_closed_tokens',
        defaults={
            'name': "Tokens d'estat de tall considerats tancats/finalitzats",
            'value': '-1,2,3',
        },
    )


def delete_closed_tokens_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token='supply_cut_status_closed_tokens').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0121_companybankrouting_and_more'),
    ]

    operations = [
        migrations.RunPython(create_closed_tokens_config, delete_closed_tokens_config),
    ]