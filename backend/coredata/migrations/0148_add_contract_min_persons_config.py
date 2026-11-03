from django.db import migrations


def add_contract_min_persons_config(apps, schema_editor):
    ConfigProject = apps.get_model('coredata', 'ConfigProject')
    configs = ConfigProject.objects.using(schema_editor.connection.alias)
    if not configs.filter(token='contract_min_persons').exists():
        configs.create(
            token='contract_min_persons',
            name="Mínim de persones d'un contracte (persons_min a les fórmules i valor quan el contracte no en té)",
            value='3',
        )


class Migration(migrations.Migration):

    dependencies = [
        ('coredata', '0147_merge_20261028_0908'),
    ]

    operations = [
        # No eliminem configuració existent si es reverteix la migració.
        migrations.RunPython(add_contract_min_persons_config, migrations.RunPython.noop),
    ]
