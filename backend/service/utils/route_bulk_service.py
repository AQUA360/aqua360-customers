"""
Operacions massives sobre rutes: inserir posicions desplaçant les posteriors,
afegir un carrer sencer, importar rutes des d'un Excel/CSV i assignar una ruta
pròpia a un punt de subministrament.
"""
import csv
import io
import logging
import re

from django.db import transaction
from django.db.models import Count, F, Max, Q

from coredata.models import Street
from service.models import Property, Route, RoutePosition, RouteZone, SupplyPoint
from service.utils.property_route_service import sync_property_tokens_with_route_position
from service.utils.route_positions_service import build_route_position_token
from service.utils.route_scope import effective_route_position

logger = logging.getLogger(__name__)


class RouteBulkError(ValueError):
    """Error de validació amb un missatge pensat per mostrar a l'usuari."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Posicions
# ---------------------------------------------------------------------------

def next_free_position(route):
    max_position = RoutePosition.objects.filter(route=route).aggregate(m=Max('position'))['m']
    return (max_position or 0) + 1


def count_positions_from(route, from_position):
    return RoutePosition.objects.filter(route=route, position__gte=from_position).count()


def shift_positions(route, from_position, count):
    """Desplaça +count les posicions >= from_position de la ruta i en
    regenera els identificadors. Retorna el nombre de posicions desplaçades."""
    if count <= 0:
        return 0
    qs = RoutePosition.objects.filter(route=route, position__gte=from_position)
    shifted_ids = list(qs.values_list('id', flat=True))
    if not shifted_ids:
        return 0
    qs.update(position=F('position') + count)
    _refresh_tokens(RoutePosition.objects.filter(id__in=shifted_ids).select_related('route'))
    return len(shifted_ids)


def _refresh_tokens(route_positions):
    to_update = []
    positions = list(route_positions)
    for route_position in positions:
        new_token = build_route_position_token(route_position)
        if new_token and route_position.token != new_token:
            route_position.token = new_token
            to_update.append(route_position)
    if to_update:
        RoutePosition.objects.bulk_update(to_update, ['token'])
    for route_position in positions:
        sync_property_tokens_with_route_position(route_position)


def create_position(route, position, name=None, address_source=None, notebook=None, reader_observation=None):
    """Crea una posició de ruta copiant l'adreça d'una finca (o d'una altra
    posició) si se n'indica una."""
    route_position = RoutePosition(
        route=route,
        position=position,
        name=name,
        notebook=notebook or None,
        reader_observation=reader_observation or None,
    )
    if address_source is not None:
        for field in ('address_street_id', 'address_street_number_id', 'address_postal_code_id',
                      'address_city_id', 'latitude', 'longitude'):
            setattr(route_position, field, getattr(address_source, field, None))
    route_position.token = build_route_position_token(route_position)
    route_position.save()
    return route_position


def _route_label(route):
    if not route:
        return None
    return {'id': route.id, 'token': route.token}


def _street_number_label(street_number):
    if not street_number:
        return ''
    return str(street_number)


# ---------------------------------------------------------------------------
# Afegir un carrer sencer
# ---------------------------------------------------------------------------

PARITY_ALL = 'all'
PARITY_EVEN = 'even'
PARITY_ODD = 'odd'


def _to_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise RouteBulkError(f"Valor numèric no vàlid: {value}") from None


def parse_add_street_params(data):
    street_id = _to_int(data.get('street_id'))
    if not street_id:
        raise RouteBulkError("Cal indicar el carrer.")
    params = {
        'street_id': street_id,
        'number_from': _to_int(data.get('number_from')),
        'number_to': _to_int(data.get('number_to')),
        'parity': data.get('parity') or PARITY_ALL,
        'order': data.get('order') or 'asc',
        'group_by': data.get('group_by') or 'number',
        'insert_at': _to_int(data.get('insert_at')),
        'assigned': data.get('assigned') or 'skip',
    }
    if params['parity'] not in (PARITY_ALL, PARITY_EVEN, PARITY_ODD):
        raise RouteBulkError("Paritat no vàlida.")
    if params['order'] not in ('asc', 'desc'):
        raise RouteBulkError("Ordre no vàlid.")
    if params['group_by'] not in ('number', 'property'):
        raise RouteBulkError("Agrupació no vàlida.")
    if params['assigned'] not in ('skip', 'move'):
        raise RouteBulkError("Opció de finques assignades no vàlida.")
    if params['insert_at'] is not None and params['insert_at'] < 1:
        raise RouteBulkError("La posició d'inserció ha de ser 1 o més.")
    return params


def _number_matches(number, params):
    filtered = params['number_from'] is not None or params['number_to'] is not None or params['parity'] != PARITY_ALL
    if number is None:
        # Les finques sense número només entren si no es filtra per número.
        return not filtered
    if params['number_from'] is not None and number < params['number_from']:
        return False
    if params['number_to'] is not None and number > params['number_to']:
        return False
    if params['parity'] == PARITY_EVEN and number % 2 != 0:
        return False
    if params['parity'] == PARITY_ODD and number % 2 == 0:
        return False
    return True


def build_add_street_plan(route, params):
    street = Street.objects.filter(id=params['street_id']).first()
    if not street:
        raise RouteBulkError("El carrer no existeix.")

    properties = (
        Property.objects.filter(address_street=street, is_active=True)
        .select_related('address_street_number', 'route_position__route')
        .annotate(supply_points_count=Count('supply_points', filter=Q(supply_points__is_active=True)))
    )
    properties = [p for p in properties if _number_matches(
        p.address_street_number.number if p.address_street_number else None, params)]

    def sort_key(prop):
        sn = prop.address_street_number
        number = sn.number if sn and sn.number is not None else None
        return (
            number is None,
            number if number is not None else 0,
            (sn.number_suffix or '') if sn else '',
            prop.token or '',
            prop.id,
        )

    properties.sort(key=sort_key)
    if params['order'] == 'desc':
        # Les finques sense número queden sempre al final.
        numbered = [p for p in properties if not sort_key(p)[0]]
        properties = numbered[::-1] + [p for p in properties if sort_key(p)[0]]

    groups = []
    group_index = {}
    for prop in properties:
        if params['group_by'] == 'number' and prop.address_street_number_id:
            key = ('n', prop.address_street_number_id)
        else:
            key = ('p', prop.id)
        if key not in group_index:
            group_index[key] = len(groups)
            label = f"{street} {_street_number_label(prop.address_street_number)}".strip()
            groups.append({'label': label, 'properties': []})
        groups[group_index[key]]['properties'].append(prop)

    insert_at = params['insert_at']
    start = insert_at if insert_at is not None else next_free_position(route)
    totals = {'positions': 0, 'properties': 0, 'supply_points': 0, 'moved': 0, 'skipped': 0}
    plan_positions = []
    position = start
    for group in groups:
        items = []
        for prop in group['properties']:
            current_route = prop.route_position.route if prop.route_position_id and prop.route_position else None
            if current_route and current_route.id == route.id:
                action = 'skip'
            elif current_route and params['assigned'] == 'skip':
                action = 'skip'
            elif current_route:
                action = 'move'
            else:
                action = 'add'
            items.append({'property': prop, 'action': action, 'current_route': current_route})
        active = [i for i in items if i['action'] != 'skip']
        totals['skipped'] += len(items) - len(active)
        group_position = None
        if active:
            group_position = position
            position += 1
            totals['positions'] += 1
            totals['properties'] += len(active)
            totals['moved'] += sum(1 for i in active if i['action'] == 'move')
            totals['supply_points'] += sum(i['property'].supply_points_count for i in active)
        plan_positions.append({'position': group_position, 'label': group['label'], 'items': items})

    shift = count_positions_from(route, start) if insert_at is not None and totals['positions'] else 0
    return {
        'route': route,
        'street': street,
        'insert_at': start,
        'shift': shift,
        'positions': plan_positions,
        'totals': totals,
    }


def serialize_add_street_plan(plan):
    return {
        'insert_at': plan['insert_at'],
        'shift': plan['shift'],
        'positions': [
            {
                'position': group['position'],
                'label': group['label'],
                'properties': [
                    {
                        'id': item['property'].id,
                        'token': item['property'].token,
                        'name': item['property'].name,
                        'supply_points_count': item['property'].supply_points_count,
                        'current_route': _route_label(item['current_route']),
                        'action': item['action'],
                    }
                    for item in group['items']
                ],
            }
            for group in plan['positions']
        ],
        'totals': plan['totals'],
    }


@transaction.atomic
def apply_add_street_plan(plan):
    route = plan['route']
    groups = [g for g in plan['positions'] if g['position'] is not None]
    if not groups:
        return {'created_positions': 0, 'assigned_properties': 0, 'moved': 0,
                'skipped': plan['totals']['skipped']}

    if plan['shift']:
        shift_positions(route, plan['insert_at'], len(groups))

    assigned = 0
    for group in groups:
        active = [i['property'] for i in group['items'] if i['action'] != 'skip']
        route_position = create_position(route, group['position'], name=group['label'], address_source=active[0])
        Property.objects.filter(id__in=[p.id for p in active]).update(route_position=route_position)
        assigned += len(active)
        sync_property_tokens_with_route_position(route_position)

    return {
        'created_positions': len(groups),
        'assigned_properties': assigned,
        'moved': plan['totals']['moved'],
        'skipped': plan['totals']['skipped'],
    }


# ---------------------------------------------------------------------------
# Importació de rutes (Excel / CSV)
# ---------------------------------------------------------------------------

IMPORT_COLUMNS = [
    'route_token', 'route_name', 'route_zone', 'position', 'property_token',
    'supply_point_token', 'street', 'street_number', 'notebook', 'reader_observation',
]

IMPORT_COLUMN_HELP = {
    'route_token': "Identificador de la ruta (obligatori). Si no existeix, es crea.",
    'route_name': "Nom de la ruta (només per a rutes noves).",
    'route_zone': "Identificador o nom de la zona (només per a rutes noves).",
    'position': "Número de posició. Les files amb la mateixa ruta i posició van a la mateixa parada.",
    'property_token': "Identificador de la finca.",
    'supply_point_token': "Identificador del punt de subministrament: només aquest punt va a la ruta (ruta pròpia).",
    'street': "Carrer (identificador o nom), si no s'indica finca ni punt.",
    'street_number': "Número del carrer, amb 'street'.",
    'notebook': "Llibreta de la posició.",
    'reader_observation': "Observació per al lector.",
}

COLUMN_ALIASES = {
    'ruta': 'route_token', 'route': 'route_token', 'nom_ruta': 'route_name', 'zona': 'route_zone',
    'posicio': 'position', 'posició': 'position', 'finca': 'property_token', 'property': 'property_token',
    'punt': 'supply_point_token', 'supply_point': 'supply_point_token', 'punt_subministrament': 'supply_point_token',
    'carrer': 'street', 'numero': 'street_number', 'número': 'street_number', 'llibreta': 'notebook',
    'observacio': 'reader_observation', 'observació': 'reader_observation',
}

MODE_APPEND = 'append'
MODE_REPLACE = 'replace'


def _normalize_header(value):
    key = re.sub(r'\s+', '_', str(value or '').strip().lower())
    return COLUMN_ALIASES.get(key, key)


def _cell_str(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _read_raw_rows(name, content):
    if name.endswith('.xlsx') or name.endswith('.xlsm'):
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.worksheets[0]
        raw_rows = [[_cell_str(c) for c in row] for row in sheet.iter_rows(values_only=True)]
    elif name.endswith('.xls'):
        import pandas as pd
        frame = pd.read_excel(io.BytesIO(content), header=None, dtype=object)
        raw_rows = [[_cell_str(None if pd.isna(c) else c) for c in row] for row in frame.values.tolist()]
    else:  # .csv o .txt
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('latin-1')
        sample = text[:4096]
        delimiter = ';' if sample.count(';') >= sample.count(',') else ','
        raw_rows = [[_cell_str(c) for c in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)]
    return raw_rows


def read_import_file(uploaded_file):
    """Retorna una llista de (número de fila, dict) amb les columnes normalitzades."""
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    content = uploaded_file.read()
    if not name.endswith(('.xlsx', '.xlsm', '.xls', '.csv', '.txt')):
        raise RouteBulkError("Format no suportat. Fes servir .xlsx, .xls o .csv.")
    try:
        raw_rows = _read_raw_rows(name, content)
    except Exception:
        # El detall de l'error de lectura només va al log, no a la resposta.
        logger.exception("No s'ha pogut llegir el fitxer d'importació de rutes")
        raise RouteBulkError("No s'ha pogut llegir el fitxer. Comprova que no estigui malmès.") from None

    if not raw_rows:
        raise RouteBulkError("El fitxer és buit.")
    headers = [_normalize_header(h) for h in raw_rows[0]]
    if 'route_token' not in headers:
        raise RouteBulkError("Falta la columna obligatòria 'route_token'.")
    rows = []
    for index, raw in enumerate(raw_rows[1:], start=2):
        if not any(raw):
            continue
        row = {header: (raw[i] if i < len(raw) else '') for i, header in enumerate(headers) if header}
        rows.append((index, row))
    return rows


def build_import_template():
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Rutes'
    sheet.append(IMPORT_COLUMNS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = 22
    help_sheet = workbook.create_sheet('Instruccions')
    help_sheet.append(['Columna', 'Descripció'])
    for cell in help_sheet[1]:
        cell.font = Font(bold=True)
    for column in IMPORT_COLUMNS:
        help_sheet.append([column, IMPORT_COLUMN_HELP[column]])
    help_sheet.append([])
    help_sheet.append(['Mode afegir', "Les posicions del fitxer s'afegeixen al final de cada ruta, en l'ordre de la columna position."])
    help_sheet.append(['Mode substituir', "Es buiden les rutes del fitxer i es creen les posicions amb els números indicats."])
    help_sheet.column_dimensions['A'].width = 22
    help_sheet.column_dimensions['B'].width = 100
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _find_street(value):
    streets = list(Street.objects.filter(token=value)[:2])
    if not streets:
        streets = list(Street.objects.filter(name__iexact=value)[:2])
    if len(streets) > 1:
        return None, f"Hi ha més d'un carrer '{value}'; fes servir l'identificador."
    if not streets:
        return None, f"Carrer '{value}' no trobat."
    return streets[0], None


def _find_zone(value):
    if not value:
        return None
    return (RouteZone.objects.filter(token=value, is_active=True).first()
            or RouteZone.objects.filter(name__iexact=value, is_active=True).first())


def build_import_plan(rows, mode):
    if mode not in (MODE_APPEND, MODE_REPLACE):
        raise RouteBulkError("Mode no vàlid.")

    route_tokens = {row.get('route_token') for _, row in rows if row.get('route_token')}
    routes = {r.token: r for r in Route.objects.filter(token__in=route_tokens, is_active=True)}
    property_tokens = {row.get('property_token') for _, row in rows if row.get('property_token')}
    supply_point_tokens = {row.get('supply_point_token') for _, row in rows if row.get('supply_point_token')}

    properties_by_token = {}
    for prop in Property.objects.filter(token__in=property_tokens, is_active=True).select_related('route_position__route'):
        properties_by_token.setdefault(prop.token, []).append(prop)
    supply_points_by_token = {}
    for sp in (SupplyPoint.objects.filter(token__in=supply_point_tokens, is_active=True)
               .select_related('route_position__route', 'property__route_position__route')):
        supply_points_by_token.setdefault(sp.token, []).append(sp)

    plan_rows = []
    new_routes = {}
    seen_properties = {}
    seen_supply_points = {}
    position_keys = set()

    for row_number, row in rows:
        route_token = row.get('route_token', '')
        position_raw = row.get('position', '')
        entry = {
            'row': row_number,
            'route_token': route_token,
            'position': None,
            'target': '',
            'status': 'ok',
            'action': 'none',
            'message': '',
            'properties': [],
            'supply_point': None,
            'data': row,
        }
        plan_rows.append(entry)
        messages = []
        warn = False

        def error(message):
            entry['status'] = 'error'
            entry['message'] = message

        if not route_token:
            error("Falta l'identificador de la ruta.")
            continue
        try:
            entry['position'] = _to_int(position_raw)
        except ValueError:
            error(f"Posició no vàlida: {position_raw}")
            continue
        if entry['position'] is not None and entry['position'] < 1:
            error("La posició ha de ser 1 o més.")
            continue

        if row.get('supply_point_token'):
            token = row['supply_point_token']
            entry['target'] = f"punt {token}"
            found = supply_points_by_token.get(token, [])
            if not found:
                error(f"Punt de subministrament '{token}' no trobat.")
                continue
            if len(found) > 1:
                error(f"Hi ha més d'un punt de subministrament '{token}'.")
                continue
            sp = found[0]
            if sp.id in seen_supply_points:
                error(f"El punt ja apareix a la fila {seen_supply_points[sp.id]}.")
                continue
            seen_supply_points[sp.id] = row_number
            entry['supply_point'] = sp
            if entry['action'] == 'none':
                entry['action'] = 'own_route'
            current = effective_route_position(sp)
            if current and current.route_id and current.route.token != route_token:
                messages.append(f"El punt es mourà de la ruta {current.route.token}.")
                warn = True
        else:
            if row.get('property_token'):
                token = row['property_token']
                entry['target'] = f"finca {token}"
                found = properties_by_token.get(token, [])
                if not found:
                    error(f"Finca '{token}' no trobada.")
                    continue
                if len(found) > 1:
                    error(f"Hi ha més d'una finca '{token}'.")
                    continue
                props = found
            elif row.get('street'):
                street, street_error = _find_street(row['street'])
                if street_error:
                    error(street_error)
                    continue
                number_raw = row.get('street_number', '')
                entry['target'] = f"{street} {number_raw}".strip()
                props_qs = Property.objects.filter(address_street=street, is_active=True).select_related('route_position__route')
                if number_raw:
                    match = re.match(r'^\s*(\d+)\s*(.*)$', number_raw)
                    if not match:
                        error(f"Número de carrer no vàlid: {number_raw}")
                        continue
                    props_qs = props_qs.filter(address_street_number__number=int(match.group(1)))
                    if match.group(2):
                        props_qs = props_qs.filter(address_street_number__number_suffix__iexact=match.group(2).strip())
                props = list(props_qs)
                if not props:
                    error(f"No hi ha finques a {entry['target']}.")
                    continue
            else:
                error("Cal indicar una finca, un punt de subministrament o un carrer.")
                continue

            duplicated = [p for p in props if p.id in seen_properties]
            if duplicated:
                error(f"La finca {duplicated[0].token or duplicated[0].id} ja apareix a la fila {seen_properties[duplicated[0].id]}.")
                continue
            for prop in props:
                seen_properties[prop.id] = row_number
            entry['properties'] = props
            moved = [p for p in props if p.route_position_id and p.route_position.route_id
                     and p.route_position.route.token != route_token]
            if entry['action'] == 'none':
                entry['action'] = 'move' if moved else 'add'
            if moved:
                messages.append(f"Es mouran {len(moved)} finques d'una altra ruta.")
                warn = True

        # La ruta nova es crea amb la primera fila vàlida que la fa servir:
        # les files amb error no creen rutes.
        if route_token not in routes and route_token not in new_routes:
            zone_value = row.get('route_zone', '')
            zone = _find_zone(zone_value)
            if zone_value and not zone:
                messages.append(f"Zona '{zone_value}' no trobada: la ruta es crearà sense zona.")
                warn = True
            new_routes[route_token] = {'name': row.get('route_name') or route_token, 'zone': zone}
            entry['action'] = 'create_route'
            messages.insert(0, "Es crearà la ruta.")

        position_keys.add((route_token, entry['position'] if entry['position'] is not None else ('row', row_number)))
        entry['status'] = 'warning' if warn else 'ok'
        entry['message'] = ' '.join(messages)

    valid = [r for r in plan_rows if r['status'] != 'error']
    totals = {
        'rows': len(plan_rows),
        'ok': sum(1 for r in plan_rows if r['status'] == 'ok'),
        'warnings': sum(1 for r in plan_rows if r['status'] == 'warning'),
        'errors': sum(1 for r in plan_rows if r['status'] == 'error'),
        'new_routes': len(new_routes),
        'positions': len(position_keys),
        'properties': sum(len(r['properties']) for r in valid),
        'supply_points': sum(1 for r in valid if r['supply_point']),
    }
    return {'mode': mode, 'rows': plan_rows, 'routes': routes, 'new_routes': new_routes, 'totals': totals}


def serialize_import_plan(plan):
    return {
        'rows': [
            {
                'row': r['row'],
                'route_token': r['route_token'],
                'position': r['position'],
                'target': r['target'],
                'status': r['status'],
                'action': r['action'],
                'message': r['message'],
            }
            for r in plan['rows']
        ],
        'totals': plan['totals'],
    }


def _clear_route(route):
    """Buida una ruta (mode substituir): treu finques i punts de les seves
    posicions i les elimina."""
    positions = RoutePosition.objects.filter(route=route)
    Property.objects.filter(route_position__in=positions).update(route_position=None)
    SupplyPoint.objects.filter(route_position__in=positions).update(route_position=None)
    positions.delete()


@transaction.atomic
def apply_import_plan(plan):
    routes = dict(plan['routes'])
    routes_created = 0
    for token, data in plan['new_routes'].items():
        routes[token] = Route.objects.create(token=token, name=data['name'], route_zone=data['zone'])
        routes_created += 1

    valid = [r for r in plan['rows'] if r['status'] != 'error']
    by_route = {}
    for entry in valid:
        by_route.setdefault(entry['route_token'], []).append(entry)

    positions_created = 0
    properties_assigned = 0
    supply_points_assigned = 0

    for token, entries in by_route.items():
        route = routes[token]
        if plan['mode'] == MODE_REPLACE and token not in plan['new_routes']:
            _clear_route(route)

        # Agrupa per posició mantenint l'ordre del fitxer; les files sense
        # posició són cadascuna una parada pròpia, després de les numerades.
        groups = {}
        for entry in entries:
            key = entry['position'] if entry['position'] is not None else ('row', entry['row'])
            groups.setdefault(key, []).append(entry)
        numbered = sorted([k for k in groups if not isinstance(k, tuple)])
        unnumbered = [k for k in groups if isinstance(k, tuple)]

        if plan['mode'] == MODE_REPLACE:
            assigned_numbers = {k: k for k in numbered}
            next_number = (max(numbered) if numbered else 0) + 1
        else:
            next_number = next_free_position(route)
            assigned_numbers = {}
            for k in numbered:
                assigned_numbers[k] = next_number
                next_number += 1
        for k in unnumbered:
            assigned_numbers[k] = next_number
            next_number += 1

        for key in numbered + unnumbered:
            group = groups[key]
            first = group[0]
            address_source = (first['properties'][0] if first['properties']
                              else (first['supply_point'].property if first['supply_point'] else None))
            route_position = create_position(
                route,
                assigned_numbers[key],
                name=first['target'] or None,
                address_source=address_source,
                notebook=first['data'].get('notebook'),
                reader_observation=first['data'].get('reader_observation'),
            )
            positions_created += 1
            property_ids = [p.id for e in group for p in e['properties']]
            if property_ids:
                Property.objects.filter(id__in=property_ids).update(route_position=route_position)
                properties_assigned += len(property_ids)
            supply_point_ids = [e['supply_point'].id for e in group if e['supply_point']]
            if supply_point_ids:
                SupplyPoint.objects.filter(id__in=supply_point_ids).update(route_position=route_position)
                supply_points_assigned += len(supply_point_ids)
            sync_property_tokens_with_route_position(route_position)

    return {
        'routes_created': routes_created,
        'positions_created': positions_created,
        'properties_assigned': properties_assigned,
        'supply_points_assigned': supply_points_assigned,
        'skipped': plan['totals']['errors'],
    }


# ---------------------------------------------------------------------------
# Ruta pròpia d'un punt de subministrament
# ---------------------------------------------------------------------------

def _delete_if_empty(route_position):
    if route_position is None:
        return
    if not route_position.properties.exists() and not route_position.supply_points.exists():
        route_position.delete()


@transaction.atomic
def set_supply_point_route(supply_point, route, position=None):
    """Assigna una ruta pròpia al punt (route=None el torna a la ruta de la finca).

    - Si la ruta és la mateixa que la de la finca, el punt simplement hereta.
    - Si un altre punt de la mateixa finca ja té posició pròpia en aquesta
      ruta, es reutilitza la mateixa parada.
    - Si no, es crea una posició nova a `position` (desplaçant les posteriors)
      o al final de la ruta.
    """
    previous = supply_point.route_position
    prop = supply_point.property

    property_route_position = prop.route_position if prop else None
    if route is None or (property_route_position and property_route_position.route_id == route.id):
        supply_point.route_position = None
        supply_point.save(update_fields=['route_position', 'updated_at'])
        if previous and previous != property_route_position:
            _delete_if_empty(previous)
        return supply_point

    if previous and previous.route_id == route.id and position in (None, previous.position):
        return supply_point

    target = None
    if prop and position is None:
        candidates = RoutePosition.objects.filter(route=route, supply_points__property=prop)
        if previous:
            candidates = candidates.exclude(id=previous.id)
        target = candidates.first()
    if target is None:
        if position is None:
            position = next_free_position(route)
        elif RoutePosition.objects.filter(route=route, position=position).exists():
            shift_positions(route, position, 1)
        label = str(prop) if prop else (supply_point.token or None)
        target = create_position(route, position, name=label, address_source=prop)

    supply_point.route_position = target
    supply_point.save(update_fields=['route_position', 'updated_at'])
    if previous and previous != target:
        _delete_if_empty(previous)
    return supply_point
