from django.db import migrations


def rename_giswater_causes(apps, schema_editor):
    """Marca l'origen Giswater dels motius Accidental/Planificada al nom, per
    distingir-los dels motius creats manualment al PA. Sols el text visible:
    el token (que fa de clau del mapa `giswater_mincut_cause_map`) no canvia."""
    SupplyCutCause = apps.get_model('service', 'SupplyCutCause')
    for token, name in [
        ('Accidental', 'Accidental (giswater)'),
        ('Planificada', 'Planificada (giswater)'),
    ]:
        SupplyCutCause.objects.filter(token=token).update(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0126_supply_cut_catalog_flags_and_remap'),
    ]

    operations = [
        migrations.RunPython(rename_giswater_causes, migrations.RunPython.noop),
    ]