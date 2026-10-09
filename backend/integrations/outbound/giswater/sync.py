from django.conf import settings
from django.db import transaction
from django.utils import timezone
from numpy import extract

from service.models import Connection, SupplyPoint
from service.models import SupplyCut, SupplyCutCause, SupplyCutStatus

from .mappers import (
    build_connection_updates_by_token,
    extract_connec_fields,
    extract_fields,
    map_mincut_to_supply_cut_dates,
)

from .services import fetch_connecs, fetch_om_mincuts, fetch_mincut_causes
from .services import fetch_mincut_states, fetch_om_mincut_connecs


def sync_connections_from_giswater():
    response = fetch_connecs()
    fields = extract_connec_fields(response)
    updates_by_token, skipped = build_connection_updates_by_token(fields)

    stats = {
        "total_fields": len(fields),
        "esco_tokens": len(updates_by_token),
        "skipped": skipped,
        "updated": 0,
        "not_found": 0,
        "unchanged": 0,
        "not_found_tokens": [],
    }

    if not updates_by_token:
        return stats

    customer_codes = list(updates_by_token.keys())
    connections = Connection.objects.filter(
        token__in=customer_codes,
        is_active=True,
    )

    connections_by_token: dict[str, list[Connection]] = {}
    for connection in connections:
        connections_by_token.setdefault(connection.token, []).append(connection)

    to_update: list[Connection] = []
    now = timezone.now()

    with transaction.atomic():
        for customer_code, values in updates_by_token.items():
            matched_connections = connections_by_token.get(customer_code, [])
            if not matched_connections:
                stats["not_found"] += 1
                stats["not_found_tokens"].append(
                    {
                        "customer_code": customer_code,
                        "code_gis": values["code_gis"],
                        "latitude": values["latitude"],
                        "longitude": values["longitude"],
                    }
                )
                continue

            for connection in matched_connections:
                changed = False

                if connection.code_gis != values["code_gis"]:
                    connection.code_gis = values["code_gis"]
                    changed = True

                if connection.latitude != values["latitude"]:
                    connection.latitude = values["latitude"]
                    changed = True

                if connection.longitude != values["longitude"]:
                    connection.longitude = values["longitude"]
                    changed = True

                if changed:
                    connection.updated_at = now
                    to_update.append(connection)
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1

        if to_update:
            Connection.objects.bulk_update(
                to_update,
                ["code_gis", "latitude", "longitude", "updated_at"],
            )

    return stats


def is_giswater_sync_enabled() -> bool:
    return getattr(settings, "GISWATER_SYNC_CONNECS_ENABLED", False)


def _catalog_key(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_mincut_config_maps():
    """Carrega els dos mapes JSON de ConfigProject (`coredata`): estat i motiu.

    Aquests mapes són EXPLÍCITS i per significat (se sembren a la migració
    0125_giswater_mincut_explicit_maps i es poden restablir amb
    `review_supply_cuts --refresh`): clau = valor de Giswater (id numèric o
    idval), valor = token del catàleg del PA. El resolver NOMÉS els llegeix;
    cap valor de Giswater no pot encunyar mai una fila de catàleg.
    """
    from django.core.serializers.json import json
    from coredata.models import ConfigProject

    maps = {}
    for token in ("giswater_mincut_state_map", "giswater_mincut_cause_map"):
        row = ConfigProject.objects.filter(token=token).first()
        try:
            maps[token] = json.loads(row.value) if row else {}
        except (TypeError, ValueError):
            maps[token] = {}
    return maps


def _resolve_catalog_with_map(mapping, model, value):
    """Resol un valor de Giswater (token o idval) cap a una fila de catàleg del
    PA usant EXCLUSIVAMENT els mapes ConfigProject. MAI crea res.

    Un valor BUIT (`None`/espais) es considera *resolt sense FK* i retorna
    `(None, True)`: no genera revisió. Només un valor NO buit i NO mapejat
    retorna `(None, False)` i deixa el mincut en revisió manual.
    """
    key = _catalog_key(value)
    if key is None:
        return None, True
    token = mapping.get(key)
    if token is None:
        return None, False
    instance = model.objects.filter(token=token).first()
    return instance, instance is not None


def sync_supply_cuts_from_giswater():
    # Els mapes (estat/motiu) són EXPLÍCITS a ConfigProject (migracions 0125/0126
    # `giswater_mincut_explicit_maps`/`_catalog_flags_and_remap`), per significat
    # i no per identitat. El resolver NOMÉS els llegeix: cap valor de Giswater no
    # pot encunyar mai una fila nova de catàleg. Si un valor no està mapejat, el
    # mincut queda en revisió manual (requires_review=True) i es conserva el
    # valor cru (`cause_raw`/`state_raw`). Els valors BUITS no generen revisió.
    # Un estat resolt cap a «Conflicte» (token 5, requires_review al catàleg)
    # resol la FK i alhora entra a quarantena fins que un operari l'assigni a un
    # estat vàlid. Un tall corregit a mà (requires_review=False amb
    # cause/status assignats) no es torna a resoldre ni es desfà.
    maps = _load_mincut_config_maps()
    state_map = maps.get("giswater_mincut_state_map", {})
    cause_map = maps.get("giswater_mincut_cause_map", {})

    print("1) Mapes de catàleg de Giswater (ConfigProject / coredata)")
    print(f"   · {len(state_map)} estats · {len(cause_map)} motius mapejats")

    response = fetch_om_mincuts()
    mincuts = extract_fields(response)

    print(f"2) Sincronitzant {len(mincuts)} mincuts…")
    stats = {
        "total_fields": len(mincuts),
        "unresolved": 0,
        "resolved": 0,
    }
    with transaction.atomic():
        existing_by_token = {
            cut.token: cut
            for cut in SupplyCut.objects.filter(
                token__in=[m.get("id") for m in mincuts if m.get("id")]
            )
        }
        causes_cache = {}
        states_cache = {}
        for mincut in mincuts:
            id = mincut.get('id')
            anl_cause = mincut.get('anl_cause')
            state = mincut.get('state')

            prev = existing_by_token.get(id)
            manual_override = (
                prev is not None
                and not prev.requires_review
                and (prev.cause_id or prev.status_id)
            )

            if manual_override:
                print(f"   = mincut {id}: correcció manual detectada; no es torna a resoldre")
                stats["resolved"] += 1
                sc = prev
            else:
                cause, cause_resolved = _resolve_catalog_with_map(
                    cause_map, SupplyCutCause, anl_cause
                )
                status, status_resolved = _resolve_catalog_with_map(
                    state_map, SupplyCutStatus, state
                )

                resolved = cause_resolved and status_resolved
                if resolved:
                    stats["resolved"] += 1
                else:
                    stats["unresolved"] += 1
                    print(
                        f"   ! mincut {id}: motiu {anl_cause!r} / estat {state!r} "
                        "no mapejats → queda en revisió manual (MAI s'auto-activa)"
                    )

                defaults = {
                    "cause": cause,
                    "status": status,
                    "cause_raw": anl_cause,
                    "state_raw": state,
                    "mincut_cause_token": cause.token if cause else None,
                    "mincut_state_token": status.token if status else None,
                    # En quarantena si el valor no es pot mapejar O l'estat del
                    # catàleg que hi correspon ho requereix (Conflicte, token 5):
                    # es resol la FK i alhora el mincut queda marcat per revisió.
                    "requires_review": (not resolved) or (
                        status is not None and status.requires_review
                    ),
                    "source": SupplyCut.SOURCE_GISWATER,
                }
                sc, created = SupplyCut.objects.update_or_create(
                    token=id,
                    defaults={**defaults, **map_mincut_to_supply_cut_dates(mincut)},
                )

            response = fetch_om_mincut_connecs(id)
            connec_fields = extract_fields(response)

            supply_points = []
            for gw_connec in connec_fields:
                connec_id = gw_connec.get('connec_id')
                supply_points.extend(
                    SupplyPoint.objects.filter(connection__code_gis=str(connec_id))
                )

            sc.supply_points.set(supply_points)

    return stats