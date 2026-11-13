from django.db import migrations


TOKEN = 'budget_due_date_days'


def create_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.get_or_create(
        token=TOKEN,
        defaults={
            'name': 'Dies de venciment per defecte dels pressupostos',
            'value': '60',
        },
    )


def delete_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    ConfigProject.objects.filter(token=TOKEN).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0340_unpaid_fee_run'),
    ]

    operations = [
        migrations.RunPython(create_config, delete_config),
    ]
