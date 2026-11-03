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


def is_supply_cut_manual_sync_enabled() -> bool:
    """Botó «Sincronitzar amb GIS Water» de la llista de talls (ConfigProject)."""
    from coredata.models import ConfigProject

    config = ConfigProject.objects.filter(token="giswater_supply_cut_sync_enabled").first()
    return bool(config and str(config.value).strip().lower() in ("true", "1", "yes"))


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


GISWATER_SYNC_OBSERVATION = "Sincronització amb Giswater"
GISWATER_DATE_FIELDS = ("date_start", "date_end", "exec_start", "exec_end")


def _gis_supply_points(connec_ids):
    if not connec_ids:
        return []
    return list(SupplyPoint.objects.filter(connection__code_gis__in=connec_ids))


def _connec_ids_from_response(response):
    """Connexions d'un mincut, o `None` si la resposta no porta `body.data.fields`.

    Una llista buida és una resposta vàlida (el mincut no afecta cap connexió);
    una resposta sense `fields` no ho és i no ha de buidar els punts del tall.
    """
    body = response.get("body") if isinstance(response, dict) else None
    data = body.get("data") if isinstance(body, dict) else None
    fields = data.get("fields") if isinstance(data, dict) else None
    if not isinstance(fields, list):
        return None
    return sorted({
        str(c.get("connec_id"))
        for c in fields
        if isinstance(c, dict) and c.get("connec_id") is not None
    })


def _create_supply_cut(token, cause, status, review, raw, dates, connec_ids):
    """Mincut nou: es crea tal com l'envia Giswater i el seu estat inicial té
    els mateixos efectes sobre els punts que un canvi d'estat a Customers."""
    from logger.models import LogSupplyCutStatus
    from service.utils import supply_cut_service

    sc = SupplyCut.objects.create(
        token=token,
        cause=cause,
        status=status,
        requires_review=review,
        source=SupplyCut.SOURCE_GISWATER,
        mincut_cause_token=cause.token if cause else None,
        mincut_state_token=status.token if status else None,
        giswater_connec_ids=connec_ids or [],
        **raw,
        **dates,
    )
    sc.supply_points.set(_gis_supply_points(connec_ids or []))
    if status is not None:
        supply_cut_service.sync_supply_points_status(
            sc, previous_status=None, observation=GISWATER_SYNC_OBSERVATION
        )
        LogSupplyCutStatus.objects.create(
            object=sc, previous_status=None, current_status=status,
            observation=GISWATER_SYNC_OBSERVATION,
        )
    return sc


def _update_supply_cut(sc, cause, cause_resolved, status, status_resolved, raw, dates, connec_ids):
    """Mincut existent: Customers té prioritat camp a camp.

    - Els camps a `customers_locked_fields` (modificats a Customers) no es toquen.
    - Una data buida de Giswater no esborra la que ja té el tall.
    - Punts: si no estan protegits, el tall queda amb els punts que envia
      Giswater; si ho estan, només s'hi afegeixen les connexions noves respecte
      de l'última sincronització (mai se'n treu cap).
    - Els canvis d'estat i de motiu, i els punts afegits o trets, passen per la
      mateixa màquina d'estats que Customers (tallar/restaurar i historial).
    """
    from logger.models import LogSupplyCutStatus
    from service.utils import supply_cut_service

    locked = set(sc.customers_locked_fields or [])
    previous_status = sc.status
    previous_temporary = supply_cut_service.is_temporary_cause(sc)

    for field, value in raw.items():
        setattr(sc, field, value)
    if "cause" not in locked and cause_resolved:
        sc.cause = cause
        sc.mincut_cause_token = cause.token if cause else None
    if "status" not in locked:
        if status_resolved:
            sc.status = status
            sc.mincut_state_token = status.token if status else None
        # Quarantena si Giswater envia valors no mapejats o un estat que ho
        # requereix (Conflicte). Si l'estat ja l'ha decidit Customers, es manté.
        sc.requires_review = (
            not (cause_resolved or "cause" in locked)
            or not status_resolved
            or (sc.status is not None and sc.status.requires_review)
        )
    for field in GISWATER_DATE_FIELDS:
        if field not in locked and dates.get(field) is not None:
            setattr(sc, field, dates[field])
    sc.save()

    current = set(sc.supply_points.values_list("id", flat=True))
    if connec_ids is None:
        # Resposta de connexions invàlida: els punts del tall no es toquen.
        to_add, to_remove = set(), set()
    elif "supply_points" in locked:
        known = set(sc.giswater_connec_ids or [])
        # Sense referència d'una sincronització anterior no es pot saber quines
        # connexions són noves: aquesta passada només la desa.
        new_connecs = [c for c in connec_ids if c not in known] if known else []
        to_add = {sp.id for sp in _gis_supply_points(new_connecs)} - current
        to_remove = set()
    else:
        gis_points = {sp.id for sp in _gis_supply_points(connec_ids)}
        to_add = gis_points - current
        to_remove = current - gis_points

    if to_remove:
        supply_cut_service.remove_supply_points_from_cut(
            sc, list(to_remove), observation=GISWATER_SYNC_OBSERVATION
        )
    if to_add:
        sc.supply_points.add(*to_add)

    supply_cut_service.sync_supply_points_status(
        sc, previous_status=previous_status, previous_temporary=previous_temporary,
        observation=GISWATER_SYNC_OBSERVATION,
    )
    if to_add and supply_cut_service.affects_sp_status(sc):
        # Estat sense canvis però tall actiu: també es tallen els punts afegits.
        supply_cut_service.cut_supply_points(sc.id, observation=GISWATER_SYNC_OBSERVATION)
    if sc.status != previous_status:
        LogSupplyCutStatus.objects.create(
            object=sc, previous_status=previous_status, current_status=sc.status,
            observation=GISWATER_SYNC_OBSERVATION,
        )

    if connec_ids is not None:
        sc.giswater_connec_ids = connec_ids
        sc.save(update_fields=["giswater_connec_ids", "updated_at"])
    return sc


def sync_supply_cuts_from_giswater():
    # Els mapes (estat/motiu) són EXPLÍCITS a ConfigProject (migracions 0125/0126
    # `giswater_mincut_explicit_maps`/`_catalog_flags_and_remap`), per significat
    # i no per identitat. El resolver NOMÉS els llegeix: cap valor de Giswater no
    # pot encunyar mai una fila nova de catàleg. Si un valor no està mapejat, el
    # mincut queda en revisió manual (requires_review=True) i es conserva el
    # valor cru (`cause_raw`/`state_raw`). Els valors BUITS no generen revisió.
    # Un estat resolt cap a «Conflicte» (token 5, requires_review al catàleg)
    # resol la FK i alhora entra a quarantena fins que un operari l'assigni a un
    # estat vàlid. Customers té prioritat: els camps modificats aquí
    # (`customers_locked_fields`) no es tornen a sobreescriure.
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
        "created": 0,
        "updated": 0,
    }
    # Les crides a Giswater es fan abans d'obrir la transacció: així els talls
    # només queden bloquejats el temps d'aplicar els canvis.
    connecs_by_mincut = {}
    for mincut in mincuts:
        id = mincut.get('id')
        connec_ids = _connec_ids_from_response(fetch_om_mincut_connecs(id))
        if connec_ids is None:
            print(f"   ! mincut {id}: resposta de connexions sense 'fields' → no es toquen els punts")
        connecs_by_mincut[id] = connec_ids

    with transaction.atomic():
        # Bloqueig de les files: una edició simultània a Customers (i la seva
        # protecció de camps) espera que acabi la sincronització, i a l'inrevés.
        existing_by_token = {
            cut.token: cut
            for cut in SupplyCut.objects.select_for_update(of=("self",))
            .select_related("status", "cause")
            .filter(token__in=[m.get("id") for m in mincuts if m.get("id")])
        }
        for mincut in mincuts:
            id = mincut.get('id')
            anl_cause = mincut.get('anl_cause')
            state = mincut.get('state')

            cause, cause_resolved = _resolve_catalog_with_map(
                cause_map, SupplyCutCause, anl_cause
            )
            status, status_resolved = _resolve_catalog_with_map(
                state_map, SupplyCutStatus, state
            )
            if cause_resolved and status_resolved:
                stats["resolved"] += 1
            else:
                stats["unresolved"] += 1
                print(
                    f"   ! mincut {id}: motiu {anl_cause!r} / estat {state!r} "
                    "no mapejats → queda en revisió manual (MAI s'auto-activa)"
                )

            raw = {"cause_raw": anl_cause, "state_raw": state}
            dates = map_mincut_to_supply_cut_dates(mincut)
            connec_ids = connecs_by_mincut.get(id)

            prev = existing_by_token.get(id)
            if prev is None:
                review = not (cause_resolved and status_resolved) or (
                    status is not None and status.requires_review
                )
                _create_supply_cut(id, cause, status, review, raw, dates, connec_ids)
                stats["created"] += 1
            else:
                _update_supply_cut(
                    prev, cause, cause_resolved, status, status_resolved, raw, dates, connec_ids
                )
                stats["updated"] += 1

    return stats
