import json

from django.db import migrations, models


# ---------------------------------------------------------------------------
# Catàleg d'estats i motius de tall — versió definitiva (0126).
#
# - Estats que QUEDEN: 0=Planificada, 1=Actiu (default), 2=Acabat, 3=Cancel·lat
#   i 5=Conflicte (sentinella, requires_review). S'ELIMINEN els tokens
#   «pendent», «-1» (innactiu) i «4» (Sobre la planificació, ara és
#   Planificada). El remap es fa abans d'esborrar, amb assert de saldo zero per
#   evitar FKs nul·les en silenci (on_delete=SET_NULL) sobre SupplyCut i
#   SupplyCutObservation.
# - Motius que QUEDEN: 0..5 + Accidental i Planificada (afegits). Els puntuals
#   (Accidental, Planificada, Manteniment o obres) porten is_temporary=True i
#   no alteren l'estat del punt de subministrament.
# - Config: desapareixen els tokens pending/innactive i el tancat passa a ser
#   {2, 3}; mapes explícits per significat (els mateixos literals de
#   review_supply_cuts --refresh).
# ---------------------------------------------------------------------------

STATUS_CATALOG = [
    {'token': '0', 'name': 'Planificada', 'color': None, 'position': None, 'is_default': False, 'requires_review': False},
    {'token': '1', 'name': 'Actiu', 'color': 'red', 'position': None, 'is_default': True, 'requires_review': False},
    {'token': '2', 'name': 'Acabat', 'color': None, 'position': None, 'is_default': False, 'requires_review': False},
    {'token': '3', 'name': 'Cancel·lat', 'color': None, 'position': None, 'is_default': False, 'requires_review': False},
    {'token': '5', 'name': 'Conflicte', 'color': None, 'position': None, 'is_default': False, 'requires_review': True},
]

CAUSE_CATALOG = [
    {'token': '0', 'name': 'Altres', 'color': None, 'is_temporary': False},
    {'token': '1', 'name': 'Impagament de Factures', 'color': 'red', 'is_temporary': False},
    {'token': '2', 'name': 'Ús no autoritzat', 'color': 'red', 'is_temporary': False},
    {'token': '3', 'name': 'Problemes de seguretat', 'color': 'yellow', 'is_temporary': False},
    {'token': '4', 'name': 'Manteniment o obres', 'color': 'blue', 'is_temporary': True},
    {'token': '5', 'name': 'Baixa de contracte', 'color': 'yellow', 'is_temporary': False},
    {'token': 'Accidental', 'name': 'Accidental', 'color': None, 'is_temporary': True},
    {'token': 'Planificada', 'name': 'Planificada', 'color': None, 'is_temporary': True},
]

# Token antic -> token nou. «pendent» i «Sobre la planificació» passen a la
# Planificada (0); «-1»/innactiu passa a Acabat (2).
LEGACY_STATUS_REMAP = {
    'pendent': '0',
    '-1': '2',
    '4': '0',
}


def seed_catalog_and_flags(apps, schema_editor):
    """Crea (si no existeix) les files del catàleg i aplica noms/colors/flags."""
    SupplyCutStatus = apps.get_model('service', 'SupplyCutStatus')
    SupplyCutCause = apps.get_model('service', 'SupplyCutCause')

    for data in STATUS_CATALOG:
        SupplyCutStatus.objects.update_or_create(
            token=data['token'],
            defaults={k: v for k, v in data.items() if k != 'token'},
        )
    for data in CAUSE_CATALOG:
        SupplyCutCause.objects.update_or_create(
            token=data['token'],
            defaults={k: v for k, v in data.items() if k != 'token'},
        )


def remap_and_delete_legacy_statuses(apps, schema_editor):
    """Remapeja els talls i observacions dels estats antics i els esborra amb
    saldo zero garantit (evita FKs nul·les en silenci amb on_delete=SET_NULL)."""
    SupplyCut = apps.get_model('service', 'SupplyCut')
    SupplyCutObservation = apps.get_model('service', 'SupplyCutObservation')
    SupplyCutStatus = apps.get_model('service', 'SupplyCutStatus')

    # Els talls mapejats antigament al token «4» (Sobre la planificació)
    # registraven mincut_state_token='4'; passa a Planificada (0).
    SupplyCut.objects.filter(mincut_state_token='4').update(mincut_state_token='0')

    for old_token, new_token in LEGACY_STATUS_REMAP.items():
        old = SupplyCutStatus.objects.filter(token=old_token).first()
        new = SupplyCutStatus.objects.filter(token=new_token).first()
        if old is None or new is None:
            continue
        SupplyCut.objects.filter(status=old).update(status=new)
        SupplyCutObservation.objects.filter(status=old).update(status=new)

    legacy = ['pendent', '-1', '4']
    orphan_cuts = SupplyCut.objects.filter(status__token__in=legacy).count()
    orphan_observations = SupplyCutObservation.objects.filter(status__token__in=legacy).count()
    if orphan_cuts or orphan_observations:
        raise AssertionError(
            f"Remap incomplet: {orphan_cuts} tall(s) i {orphan_observations} "
            f"observació(ons) encara apunten a un estat antic ({legacy})."
        )

    deleted = SupplyCutStatus.objects.filter(token__in=legacy).delete()[0]
    print(f"   Estats antics eliminats: {deleted} fila(s).")


def seed_config_and_maps(apps, schema_editor):
    """ConfigProject: fora pending/innactive; tancats={2, 3}; mapes explícits."""
    ConfigProject = apps.get_model('coredata', 'ConfigProject')

    ConfigProject.objects.filter(
        token__in=['supply_cut_status_pending_token', 'supply_cut_status_innactive_token']
    ).delete()

    ConfigProject.objects.update_or_create(
        token='supply_cut_status_closed_tokens',
        defaults={
            'name': "Tokens d'estat de tall considerats tancats/finalitzats",
            'value': '2,3',
        },
    )

    state_map = {
        "0": "0", "Planificada": "0", "4": "0", "Sobre la planificació": "0",
        "1": "1", "En curs": "1",
        "2": "2", "Acabat": "2",
        "3": "3", "Cancel·lat": "3",
        "5": "5", "Conflicte": "5",
    }
    cause_map = {
        "1": "Accidental", "Accidental": "Accidental",
        "2": "Planificada", "Planificada": "Planificada",
    }
    ConfigProject.objects.update_or_create(
        token='giswater_mincut_state_map',
        defaults={
            'name': "Mapa d'estat de Giswater -> token del catàleg d'estat del PA",
            'value': json.dumps(state_map, ensure_ascii=False),
        },
    )
    ConfigProject.objects.update_or_create(
        token='giswater_mincut_cause_map',
        defaults={
            'name': "Mapa de motiu de Giswater -> token del catàleg de motiu del PA",
            'value': json.dumps(cause_map, ensure_ascii=False),
        },
    )


def backfill_conflicte_review(apps, schema_editor):
    """Els talls existents en estat Conflicte (5) entren a quarantena."""
    SupplyCut = apps.get_model('service', 'SupplyCut')
    SupplyCut.objects.filter(status__token='5', requires_review=False).update(
        requires_review=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ('service', '0125_giswater_mincut_explicit_maps'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplycutstatus',
            name='requires_review',
            field=models.BooleanField(
                default=False,
                help_text="L'estat entra a quarantena: el tall no s'auto-activa/tanca "
                          "ni toca els punts de subministrament fins que un operari "
                          "l'assigni manualment a un estat vàlid.",
            ),
        ),
        migrations.AddField(
            model_name='supplycutcause',
            name='is_temporary',
            field=models.BooleanField(
                default=False,
                help_text="El tall és puntual (previst amb dates o accidental): NO "
                          "altera l'estat del punt de subministrament ni genera avís "
                          "SMS. Fals = tall indefinit (Impagament, seguretat, ...).",
            ),
        ),
        migrations.RunPython(seed_catalog_and_flags, migrations.RunPython.noop),
        migrations.RunPython(remap_and_delete_legacy_statuses, migrations.RunPython.noop),
        migrations.RunPython(seed_config_and_maps, migrations.RunPython.noop),
        migrations.RunPython(backfill_conflicte_review, migrations.RunPython.noop),
    ]