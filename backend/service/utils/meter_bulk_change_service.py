"""
service/utils/meter_bulk_change_service.py

Canvi massiu de comptadors des de CSV/Excel. Reutilitza MeterChangeService
(el mateix que fa servir el flux d'ordres de treball), una crida per fila.

Columnes del fitxer (la capçalera és la primera fila):
  code                obligatòria  codi del comptador actual (el que es retira)
  new_code            obligatòria  codi del comptador nou
  final_reading       obligatòria  lectura de tancament del vell (0 és vàlid)
  initial_reading     obligatòria  lectura inicial del nou (0 és vàlid)
  create_new_meter    opcional     si/no: "si" => el comptador nou NO existeix i
                                   s'ha de crear. Buit = no.
  change_date         opcional     YYYY-MM-DD o DD/MM/YYYY; per defecte avui
  supply_point        opcional     token del punt; només si el vell és a més d'un
  caliber             opcional     diàmetre del comptador nou (només si es crea)
  has_remote_reading  opcional     si/no, telelectura (només si es crea)
  comm_technology     opcional     tipus de comunicació de la telelectura (només si es crea)

Decisions:
  - create_new_meter = si i el codi ja existeix  => error (evita duplicats per equivocació).
  - create_new_meter = no i el codi no existeix  => error amb indicació de posar "si".
  - Crear el comptador i fer el canvi van dins la MATEIXA transacció per fila:
    si el canvi falla, el comptador creat es desfà.
  - Confirm parcial: les files que fallen es retornen a `errors`.
  - Si es dóna comm_technology i has_remote_reading és buit, s'assumeix telelectura = si.
    Si has_remote_reading = no i hi ha comm_technology => error.
  - Camps opcionals amb valor que s'ignoren (el comptador ja existeix) => avís.
"""
import datetime
import io
import logging
import re
from collections import Counter, defaultdict

import pandas as pd
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from coredata.models import ConfigProject
from service.models import Meter, MeterStatus, SupplyPoint
from service.services.meter_change_service import MeterChangeService

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ['code', 'new_code', 'final_reading', 'initial_reading']
OPTIONAL_COLUMNS = [
    'create_new_meter', 'change_date', 'supply_point',
    'caliber', 'has_remote_reading', 'comm_technology',
]
# TODO: comprovar que és un valor vàlid de Reading.origin (a ordres es fa servir 'order_change_meter')
ORIGIN = 'bulk_change_meter'

TRUE_VALUES = {'si', 'sí', 's', 'yes', 'y', 'true', '1'}
FALSE_VALUES = {'no', 'n', 'false', '0'}


class MeterBulkChangeError(Exception):
    """Error que impedeix processar el fitxer sencer (format, columnes...)."""


class MeterBulkChangeValidationError(MeterBulkChangeError):
    """Validació del fitxer amb un diagnòstic segur per a l’API."""


# --------------------------------------------------------------------------- #
# Lectura del fitxer i parsers de cel·les
# --------------------------------------------------------------------------- #
def _read_file(uploaded):
    name = (getattr(uploaded, 'name', '') or '').lower()
    try:
        if name.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(uploaded.read()), sep=None, engine='python', dtype=str,
                             encoding='utf-8-sig', keep_default_na=False)
        elif name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded, dtype=str, keep_default_na=False)
        else:
            raise MeterBulkChangeValidationError("Format no admès. Useu .csv, .xlsx o .xls.")
    except MeterBulkChangeError:
        raise
    except Exception as exc:
        raise MeterBulkChangeError(f"No s'ha pogut llegir el fitxer: {exc}")

    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise MeterBulkChangeValidationError(f"Falten columnes obligatòries: {', '.join(missing)}.")
    return df


def _cell(raw, column):
    value = raw.get(column, '')
    return '' if value is None else str(value).strip()


def _parse_reading(value, label):
    if value == '':
        raise ValueError(f"Falta {label}.")
    try:
        number = float(value.replace(',', '.'))
    except ValueError:
        raise ValueError(f"{label} no és un número vàlid: '{value}'.")
    if number != int(number):
        raise ValueError(f"{label} ha de ser un enter.")
    if number < 0:
        raise ValueError(f"{label} no pot ser negativa.")
    return int(number)


def _parse_date(value):
    if value == '':
        return datetime.date.today()
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}', value):
            parsed = datetime.date.fromisoformat(value[:10])
        else:
            parsed = pd.to_datetime(value, dayfirst=True).date()
    except Exception:
        raise ValueError(f"Data no vàlida: '{value}'.")
    if parsed > datetime.date.today():
        raise ValueError("La data del canvi no pot ser futura.")
    return parsed


def _parse_bool(value, label):
    """'' -> None (no informat); si/no -> True/False."""
    if value == '':
        return None
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{label} ha de ser 'si' o 'no' (valor rebut: '{value}').")


# --------------------------------------------------------------------------- #
# Dades del comptador nou
# --------------------------------------------------------------------------- #
_choice_cache = {}


def _resolve_choice(field_name, value, label):
    """
    Si el camp del model és una FK, busca el registre per token o nom (sense
    distingir majúscules). Si no ho és, retorna el text tal qual.
    """
    key = (field_name, value.lower())
    if key in _choice_cache:
        return _choice_cache[key]

    field = Meter._meta.get_field(field_name)
    if not field.is_relation:
        _choice_cache[key] = value
        return value

    model = field.related_model
    model_fields = {f.name for f in model._meta.get_fields()}
    for lookup in ('token', 'name', 'code'):
        if lookup not in model_fields:
            continue
        matches = list(model.objects.filter(**{f'{lookup}__iexact': value})[:2])
        if len(matches) == 1:
            _choice_cache[key] = matches[0]
            return matches[0]

    options = []
    for lookup in ('name', 'token'):
        if lookup in model_fields:
            options = list(model.objects.values_list(lookup, flat=True)[:12])
            break
    hint = f" Valors vàlids: {', '.join(str(o) for o in options)}." if options else ''
    raise ValueError(f"{label} '{value}' no existeix.{hint}")


def _build_new_meter_data(r):
    """Camps opcionals del comptador nou -> kwargs del model (només els informats)."""
    data = {}
    has_remote = _parse_bool(r['has_remote_reading'], 'has_remote_reading')

    if r['caliber']:
        data['caliber'] = _resolve_choice('caliber', r['caliber'], 'Diàmetre')

    if r['comm_technology']:
        if has_remote is False:
            raise ValueError("comm_technology informat però has_remote_reading és 'no'.")
        data['comm_technology'] = _resolve_choice(
            'comm_technology', r['comm_technology'], 'Tipus de comunicació')
        if has_remote is None:
            has_remote = True

    if has_remote is not None:
        data['has_remote_reading'] = has_remote
        if has_remote:
            data['has_ever_been_remote'] = True  # implícit: si ara és remot, ho ha estat
    return data


def _display(value):
    return None if value is None else (value if isinstance(value, (bool, str)) else str(value))


def _get_active_status():
    token = ConfigProject.objects.get(token='meter_status_active_token').value
    return MeterStatus.objects.get(token=token)


def _validate_new_meter(code, data, status):
    """Construeix un Meter sense desar i el valida (camps obligatoris, longituds...)."""
    meter = Meter(code=code, status=status, **data)
    try:
        meter.full_clean()
    except ValidationError as exc:
        details = '; '.join(f"{k}: {', '.join(v)}" for k, v in exc.message_dict.items())
        raise ValueError(f"No es pot crear el comptador {code}: {details}")


# --------------------------------------------------------------------------- #
# Anàlisi (compartida per preview i confirm)
# --------------------------------------------------------------------------- #
def _analyse(uploaded):
    _choice_cache.clear()
    df = _read_file(uploaded)

    rows = []
    for idx, raw in df.iterrows():
        data = {c: _cell(raw, c) for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS}
        if not any(data.values()):
            continue  # fila buida
        data['row'] = idx + 2  # +1 capçalera, +1 perquè Excel compta des d'1
        rows.append(data)
    if not rows:
        raise MeterBulkChangeValidationError("El fitxer no conté cap fila amb dades.")

    # Codis repetits (vell o nou, en qualsevol fila)
    counter = Counter()
    for r in rows:
        counter.update({c for c in (r['code'], r['new_code']) if c})
    duplicate_codes = sorted(c for c, n in counter.items() if n > 1)
    duplicate_set = set(duplicate_codes)

    # Consultes en bloc
    existing_codes = set(Meter.objects.filter(
        code__in=set(counter.keys())).values_list('code', flat=True))
    meters_by_code = defaultdict(list)
    for meter in Meter.objects.filter(code__in=set(counter.keys()), is_active=True):
        meters_by_code[meter.code].append(meter)

    meter_ids = [m.id for ms in meters_by_code.values() for m in ms]
    supply_points_by_meter = defaultdict(list)
    for sp in SupplyPoint.objects.filter(meter_id__in=meter_ids).select_related('address'):
        supply_points_by_meter[sp.meter_id].append(sp)

    active_status = None  # es carrega només si cal crear algun comptador
    changes, ready, not_found, errors = [], [], [], []

    def error(r, message):
        errors.append({'row': r['row'], 'code': r['code'] or None, 'message': message})

    for r in rows:
        code, new_code = r['code'], r['new_code']

        if not code or not new_code:
            error(r, "Falta code o new_code.")
            continue
        if code == new_code:
            error(r, "El comptador nou no pot ser el mateix que l'actual.")
            continue
        if code in duplicate_set or new_code in duplicate_set:
            continue  # ja reportat a duplicate_codes_in_file

        try:
            final_reading = _parse_reading(r['final_reading'], 'final_reading')
            initial_reading = _parse_reading(r['initial_reading'], 'initial_reading')
            change_date = _parse_date(r['change_date'])
            create_flag = bool(_parse_bool(r['create_new_meter'], 'create_new_meter'))
        except ValueError as exc:
            error(r, str(exc))
            continue

        old_candidates = meters_by_code.get(code, [])
        if not old_candidates:
            not_found.append(code)
            continue
        if len(old_candidates) > 1:
            error(r, f"Hi ha més d'un comptador actiu amb codi {code}.")
            continue
        old_meter = old_candidates[0]

        # --- Comptador nou: existent o a crear -------------------------------
        new_candidates = meters_by_code.get(new_code, [])
        if len(new_candidates) > 1:
            error(r, f"Hi ha més d'un comptador actiu amb codi {new_code}.")
            continue
        new_meter = new_candidates[0] if new_candidates else None

        meter_data = None
        warnings = []
        has_meter_data = any(r[c] for c in ('caliber', 'has_remote_reading', 'comm_technology'))

        if create_flag:
            if new_code in existing_codes:
                error(r, f"El comptador {new_code} ja existeix; poseu create_new_meter = no "
                         f"(o deixeu-lo buit) per fer-lo servir.")
                continue
            try:
                meter_data = _build_new_meter_data(r)
                if active_status is None:
                    active_status = _get_active_status()
                _validate_new_meter(new_code, meter_data, active_status)
            except ValueError as exc:
                error(r, str(exc))
                continue
        else:
            if not new_meter:
                error(r, f"El comptador nou {new_code} no existeix. Si s'ha de crear, "
                         f"poseu create_new_meter = si.")
                continue
            if has_meter_data:
                warnings.append({'code': 'meter_data_ignored', 'detail': new_code})

        # --- Punt de subministrament on es fa el canvi -----------------------
        candidates = supply_points_by_meter.get(old_meter.id, [])
        if r['supply_point']:
            candidates = [sp for sp in candidates if sp.token == r['supply_point']]
            if not candidates:
                error(r, f"El comptador {code} no és al punt de subministrament {r['supply_point']}.")
                continue
        if not candidates:
            error(r, f"El comptador {code} no està assignat a cap punt de subministrament.")
            continue
        if len(candidates) > 1:
            error(r, f"El comptador {code} és a {len(candidates)} punts de subministrament; "
                     f"indiqueu-ne un a la columna supply_point.")
            continue
        supply_point = candidates[0]

        # Avís (no bloqueja): MeterChangeService desassigna el nou d'altres punts
        if new_meter and not new_meter.is_general:
            other = supply_points_by_meter.get(new_meter.id, [])
            if other:
                warnings.append({
                    'code': 'new_meter_assigned',
                    'detail': ', '.join(sp.token for sp in other),
                })

        new_meter_info = {'will_create': meter_data is not None}
        if meter_data is not None:
            new_meter_info.update({
                'caliber': _display(meter_data.get('caliber')),
                'has_remote_reading': meter_data.get('has_remote_reading'),
                'comm_technology': _display(meter_data.get('comm_technology')),
            })

        changes.append({
            'row': r['row'],
            'code': code,
            'new_code': new_code,
            'new_meter': new_meter_info,
            'supply_point': {
                'id': supply_point.id,
                'token': supply_point.token,
                'address': str(supply_point.address) if supply_point.address else None,
            },
            'final_reading': final_reading,
            'initial_reading': initial_reading,
            'change_date': change_date.isoformat(),
            'warnings': warnings,
        })
        ready.append({
            'row': r['row'], 'code': code, 'new_code': new_code,
            'supply_point_id': supply_point.id,
            'old_meter_id': old_meter.id,
            'new_meter_id': new_meter.id if new_meter else None,
            'create_meter': meter_data,  # None si el comptador ja existeix
            'final_reading': final_reading, 'initial_reading': initial_reading,
            'change_date': change_date,
        })

    return {
        'rows': rows, 'changes': changes, 'ready': ready, 'not_found': not_found,
        'errors': errors, 'duplicate_codes': duplicate_codes, 'active_status': active_status,
    }


def _serialize(analysis, extra_stats=None):
    stats = {
        'total_rows': len(analysis['rows']),
        'to_change': len(analysis['changes']),
        'to_create': sum(1 for c in analysis['changes'] if c['new_meter']['will_create']),
        'not_found': len(analysis['not_found']),
        'errors': len(analysis['errors']),
        'duplicate_codes_in_file': len(analysis['duplicate_codes']),
    }
    stats.update(extra_stats or {})
    return {
        'stats': stats,
        'changes': analysis['changes'],
        'not_found': analysis['not_found'],
        'errors': analysis['errors'],
        'duplicate_codes_in_file': analysis['duplicate_codes'],
    }


# --------------------------------------------------------------------------- #
# API pública (la usen les vistes)
# --------------------------------------------------------------------------- #
def build_preview(uploaded):
    """Valida el fitxer sense tocar res."""
    return _serialize(_analyse(uploaded))


def apply_changes(uploaded, user):
    """
    Re-valida el fitxer i aplica cada canvi vàlid. Per fila, en una sola
    transacció: crea el comptador nou (si cal) i fa el canvi.
    """
    analysis = _analyse(uploaded)
    if any(item['create_meter'] is not None for item in analysis['ready']):
        if not user.has_perm('service.add_meter'):
            raise PermissionDenied()
    changed, created, failed = 0, 0, []

    for item in analysis['ready']:
        try:
            with transaction.atomic():
                supply_point = SupplyPoint.objects.select_for_update().get(
                    pk=item['supply_point_id'])
                if supply_point.meter_id != item['old_meter_id']:
                    failed.append({
                        'row': item['row'], 'code': item['code'],
                        'message': 'El comptador actual del punt de subministrament ha canviat.',
                    })
                    continue
                new_meter_id = item['new_meter_id']
                if item['create_meter'] is not None:
                    new_meter = Meter.objects.create(
                        code=item['new_code'],
                        status=analysis['active_status'],
                        **item['create_meter'],
                    )
                    new_meter_id = new_meter.id

                MeterChangeService(user=user).apply(
                    supply_point_id=item['supply_point_id'],
                    prev_meter_id=item['old_meter_id'],
                    new_meter_id=new_meter_id,
                    origin=ORIGIN,
                    change_date=item['change_date'],
                    previous_reading_data={
                        'reading_value': item['final_reading'],
                        # None => el servei el calcula (lectura final - lectura anterior del contracte)
                        'calculated_value': None,
                        'is_close': True,
                        'leak_value': 0,
                    },
                    new_reading_data={
                        'reading_value': item['initial_reading'],
                        'calculated_value': 0,  # lectura inicial: no hi ha consum
                        'is_close': False,
                        'leak_value': 0,
                    },
                )
            changed += 1
            if item['create_meter'] is not None:
                created += 1
        except Exception:
            logger.exception("Canvi massiu de comptador fallit (fila %s)", item['row'])
            failed.append({'row': item['row'], 'code': item['code'], 'message': "No s'ha pogut aplicar el canvi de comptador."})

    result = _serialize(analysis)
    result['errors'] = result['errors'] + failed
    result['stats'].update({
        'changed': changed,
        'created': created,
        'failed': len(failed),
        'errors': len(result['errors']),
    })
    return result