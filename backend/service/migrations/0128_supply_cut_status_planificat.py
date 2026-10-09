from django.db import migrations


def rename_planned_status(apps, schema_editor):
    """«tall de subministrament» és masculí: l'estat del catàleg passa de
    «Planificada» a «Planificat». Sols el text visible; el token '0' (clau
    dels mapes `giswater_mincut_state_map`, que fan servir el vocabulari de
    Giswater) no canvia."""
    SupplyCutStatus = apps.get_model('service', 'SupplyCutStatus')
    SupplyCutStatus.objects.filter(token='0').update(name='Planificat')


def undo_rename_planned_status(apps, schema_editor):
    SupplyCutStatus = apps.get_model('service', 'SupplyCutStatus')
    SupplyCutStatus.objects.filter(token='0').update(name='Planificada')


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0127_rename_giswater_causes'),
    ]

    operations = [
        migrations.RunPython(rename_planned_status, undo_rename_planned_status),
    ]