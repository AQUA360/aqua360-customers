import json

from django.db import migrations

# ---------------------------------------------------------------------------
# Chunk B (revisat, ancorat a la realitat) — prémer les dues filtes JSON de
# ConfigProject (`coredata`) amb el patró GMAO_STATUS_MAPPING, més quarentena
# del backlog.
#
# Regla fonamental de disseny: MAI es crea cap fila de catàleg des d'aquesta
# migració ni des del resolver. El catàleg del PA ja és first-class i cada fila
# porta el token = id numèric de Giswater (identitat). Així:
#   * els mapes es DERIVEN del catàleg real (token -> token; nom -> token) i
#   * cap valor de Giswater pot "encunyar" mai una fila nova.
#
# Backlog real (verificat a la BD): 47 talls de Giswater vençuts (date_start
# passat) amb estat `'0'`(4) o `'4'`(43) i motiu `Accidental'(47)`. -> mai
# s'auto-activen; queden en revisió manual (requires_review=True).
# ---------------------------------------------------------------------------

# Tokens d'estat del PA que signifiquen "tancat/acabats" + "actiu" (=no tall).
CLOSED_OR_ACTIVE_STATE_TOKENS = {"1", "2", "3", "-1"}


def _catalog_state_map(apps):
    """Deriva el mapa d'estat des del catàleg real del PA.

    Clau: el que Giswater pot enviar com a `state` (id numèric = token, o el
    nom/idval). Valor: el token del PA. Mai introdueix tokens que no existeixin.
    """
    SupplyCutStatus = apps.get_model("service", "SupplyCutStatus")
    mapping = {}
    for status in SupplyCutStatus.objects.order_by("id"):
        mapping[str(status.token)] = status.token
        if status.name and status.name != status.token:
            mapping[status.name] = status.token
    return mapping


def _catalog_cause_map(apps):
    """Idem per motius."""
    SupplyCutCause = apps.get_model("service", "SupplyCutCause")
    mapping = {}
    for cause in SupplyCutCause.objects.order_by("id"):
        mapping[str(cause.token)] = cause.token
        if cause.name and cause.name != cause.token:
            mapping[cause.name] = cause.token
    return mapping


def seed_maps(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.update_or_create(
        token="giswater_mincut_state_map",
        defaults={
            "name": "Mapa d'estat de Giswater -> token del catàleg d'estat del PA",
            "value": json.dumps(_catalog_state_map(apps), ensure_ascii=False),
        },
    )
    ConfigProject.objects.update_or_create(
        token="giswater_mincut_cause_map",
        defaults={
            "name": "Mapa de motiu de Giswater -> token del catàleg de motiu del PA",
            "value": json.dumps(_catalog_cause_map(apps), ensure_ascii=False),
        },
    )


def delete_maps(apps, schema_editor):
    ConfigProject = apps.get_model("coredata", "ConfigProject")
    ConfigProject.objects.filter(
        token__in=["giswater_mincut_state_map", "giswater_mincut_cause_map"]
    ).delete()


def quarantine_backlog(apps, schema_editor):
    """Quarantena del backlog de Giswater: els talls ja vençuts que no estan ni
    actius ni tancats es marquen `requires_review=True` i MAI s'auto-activen.

    NOTA (diferència respecte del resolver): aqui el criteri de "vençut" usa
    `date_start` (l'únic camp de data del backlog de Giswater depositada al PA),
    mentre que supply_cuts_due_to_activate fa servir `exec_start` per als talls
    de Giswater. És una aproximació per a la migració inicial: la següent sync
    re-avalua requires_review amb els mapes, així que aquesta fila només
    protegeix fins que els mapes hi arribin.
    """
    SupplyCut = apps.get_model("service", "SupplyCut")
    from django.utils import timezone

    today = timezone.now().date()
    backlog = (
        SupplyCut.objects.filter(source="giswater")
        .filter(date_start__date__lte=today)
        .exclude(status__token__in=CLOSED_OR_ACTIVE_STATE_TOKENS)
    )
    updated = backlog.update(requires_review=True) 
    print(
        f"   Quarentena del backlog: {updated} talls de Giswater vençuts "
        "sense resoldre marcats com a revisió manual."
    )


def undo_quarantine(apps, schema_editor):
    SupplyCut = apps.get_model("service", "SupplyCut")
    SupplyCut.objects.filter(source="giswater", requires_review=True).update(
        requires_review=False
    )


class Migration(migrations.Migration):

    dependencies = [
        ("service", "0123_supply_cut_review_tokens"),
    ]

    operations = [
        migrations.RunPython(seed_maps, delete_maps),
        migrations.RunPython(quarantine_backlog, undo_quarantine),
    ]
