import json

from django.db import migrations

# ---------------------------------------------------------------------------
# Chunk C — mapes EXPLÍCITS per significat (substitueixen la derivació per
# identitat de la migració 0124).
#
# Regla de disseny: el mapa és una traducció escrita a mà, per significat, mai
# per coincidència de dígits. GIS i el PA tenen vocabularis independents; el
# 1=1 de la causa (Accidental vs Impagament de Factures) és una col·lisió
# numèrica, no unes equivalència. Quan un id de GIS no té clau al mapa, la sync
# el deixa en quarantena (requires_review=True) i conserva el raw — mai
# s'assigna pel número ni es crea cap fila.
#
# Declarat com a literal aquí perquè les migracions siguin autocontingudes;
# `review_supply_cuts --refresh` restableix EXACTAMENT aquests mateixos mapes.
# ---------------------------------------------------------------------------

# Estats GIS (id i idval) -> token del catàleg d'estat del PA. «En curs» ==
# «Actiu» (el mateix significat operatiu) i per això es mapeja a 1.
EXPLICIT_STATE_MAP = {
    "0": "0",
    "Planificada": "0",
    "1": "1",
    "En curs": "1",
    "2": "2",
    "Acabat": "2",
    "3": "3",
    "Cancel·lat": "3",
    "4": "4",
    "Sobre la planificació": "4",
    "5": "5",
    "Conflicte": "5",
}

# Motius GIS (mincut_cause): 1=Accidental, 2=Planificada. Per significat:
# Accidental -> PA 0 (Altres); Planificada -> PA 4 (Manteniment o obres).
EXPLICIT_CAUSE_MAP = {
    "1": "0",
    "Accidental": "0",
    "2": "4",
    "Planificada": "4",
}

# Tokens PA equals (no GIS) que mai arriben per sync (es posen directament per
# FK des del serializer/tasques) i per tant s'eliminen dels mapes: Actiu,
# pendent, -1/innactiu.


def seed_explicit_maps(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.update_or_create(
        token="giswater_mincut_state_map",
        defaults={
            "name": "Mapa d'estat de Giswater -> token del catàleg d'estat del PA",
            "value": json.dumps(EXPLICIT_STATE_MAP, ensure_ascii=False),
        },
    )
    ConfigProject.objects.update_or_create(
        token="giswater_mincut_cause_map",
        defaults={
            "name": "Mapa de motiu de Giswater -> token del catàleg de motiu del PA",
            "value": json.dumps(EXPLICIT_CAUSE_MAP, ensure_ascii=False),
        },
    )


def reclassify_and_remove_ad_hoc_cause(apps, schema_editor):
    """Reassigna la causa ad hoc `Accidental` (token literal) a `Altres` (0) i
    l'elimina del catàleg. Es toca la FK directament: els talls ja tenen
    `requires_review=False` + cause_id, per tant la sync ja no els re-resoldria
    (el guard manual_override), encara que canviéssim el mapa."""
    SupplyCut = apps.get_model("service", "SupplyCut")
    SupplyCutCause = apps.get_model("service", "SupplyCutCause")

    ad_hoc = SupplyCutCause.objects.filter(token="Accidental").first()
    if ad_hoc is None:
        return
    altres = SupplyCutCause.objects.filter(token="0").first()
    if altres is None:
        return

    reclassified = SupplyCut.objects.filter(cause=ad_hoc).update(
        cause=altres,
        mincut_cause_token="0",
    )
    ad_hoc.delete()
    print(
        f"   Reclassificats {reclassified} talls a Altres (0); "
        "fila ad hoc 'Accidental' eliminada."
    )


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0124_giswater_mincut_token_maps"),
    ]

    operations = [
        migrations.RunPython(seed_explicit_maps, migrations.RunPython.noop),
        migrations.RunPython(reclassify_and_remove_ad_hoc_cause, migrations.RunPython.noop),
    ]