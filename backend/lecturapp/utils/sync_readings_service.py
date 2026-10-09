"""
Shared sync_readings logic for lecturapp (views + CSV import).
Mirrors lecturapp.views.sync_readings per-reading processing.
"""

import base64
import csv
import logging
import os
import sys
from datetime import datetime

from django.core.files.base import ContentFile

from billing.utils.reading_service import check_billing_period

logger = logging.getLogger(__name__)


def _to_float(value, default=0):
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _calculate_value(new_reading_value, previous_reading, last_reading_fallback):
    """
    Consumption delta for a reading, always derived from the previous reading
    actually being assigned to it -- never from a stale/unrelated value --
    so calculated_value stays consistent with the persisted previous_reading FK.
    """
    if new_reading_value == 0:
        return 0
    previous_reading_value = previous_reading.reading_value if previous_reading else None
    if previous_reading_value is None:
        previous_reading_value = last_reading_fallback
    return float(new_reading_value) - float(previous_reading_value)


def _is_meter_change_reading(reading):
    """
    Les lectures que marquen un canvi fisic de comptador -- el tancament del
    comptador vell (is_close=True) i la primera lectura del comptador actual
    -- son el registre del canvi, no un duplicat, i mai s'han de marcar com
    a control nomes perque cauen dins el mateix periode de facturacio que
    una lectura entrant.
    """
    from billing.models import Reading

    if reading.is_close:
        return True

    return not Reading.objects.filter(
        meter_id=reading.meter_id,
        is_active=True,
        reading_date__lt=reading.reading_date,
    ).exclude(id=reading.id).exists()


def _resolve_previous_reading(
    contract,
    supply_point,
    meter,
    reading_date,
    reading_batch,
    client_previous_reading,
    dry_run,
    exclude_reading_id=None,
):
    """
    Find the correct previous reading for a reading being created/updated by
    the lecturapp sync, scoped to the contract/supply point/meter and always
    excluding control readings.

    The client-supplied previous_reading (from previous_reading_id, e.g. the
    mobile app's locally cached value) is used only as a last resort, when
    this scoped lookup can't determine a previous reading at all -- including
    when it turns out to be a control reading: a control previous_reading is
    preferred over leaving the new reading with none at all.

    exclude_reading_id must be passed when resolving for an ALREADY-PERSISTED
    reading being updated (e.g. its date is being corrected to a later date):
    without it, the reading's own still-on-disk row can match the scoped
    query and be picked as its own previous_reading.
    """
    from billing.models import Reading

    try:
        previous_reading_qs = Reading.objects.filter(
            contract=contract,
            supply_point=supply_point,
            meter=meter,
            reading_date__lt=reading_date,
            is_control=False,
            is_active=True,
            is_close=False,
        )
        if exclude_reading_id is not None:
            previous_reading_qs = previous_reading_qs.exclude(id=exclude_reading_id)
        previous_reading = previous_reading_qs.order_by('-reading_date').first()
    except Exception as e:
        logger.warning('Error looking up previous reading for contract %s: %s', contract, e)
        previous_reading = None

    if previous_reading is not None:
        try:
            can_enter_readings = check_billing_period(
                reading_date=reading_date,
                supply_point=supply_point,
                meter=meter,
                contract=contract,
                previous_reading=previous_reading,
                is_termination=False,
            )
            if (
                not can_enter_readings
                and not previous_reading.billing_id
                and not _is_meter_change_reading(previous_reading)
                and previous_reading.batch != reading_batch
            ):
                previous_previous_reading = previous_reading.previous_reading
                if previous_previous_reading:
                    previous_reading.is_control = True
                    if not dry_run:
                        previous_reading.save()
                    previous_reading = previous_previous_reading
        except Exception as e:
            logger.warning(
                'Error checking billing period for previous reading %s: %s', previous_reading.id, e
            )
        return previous_reading

    if client_previous_reading is not None and client_previous_reading.id != exclude_reading_id:
        return client_previous_reading

    return None


def _get_reading_targets(meter, supply_point, contract_active_token):
    """
    (supply_point, contract) pairs that must get a reading when a new reading
    enters for this meter.

    Always the active contracts whose supply_point_default is the supply point
    sent by the app. When the meter is a general meter without sub-meters
    (several supply points sharing one physical meter), also every other
    active supply point with a billable contract -- the same targets as
    fanout_general_meter_readings(), so billing finds them already created
    (linked via copied_from) instead of copying the reading with the previous
    reading of another contract. Each reading keeps the full meter
    consumption: the split happens at invoice time
    (recalc_consumption_general_meter_no_submeters).
    """
    from coredata.models import ConfigProject
    from contract.models import Contract
    from service.models import SupplyPointStatus
    from billing.utils.reading_service import _get_general_meter_fanout_targets

    targets = [
        (supply_point, contract)
        for contract in Contract.objects.filter(
            status__token=contract_active_token,
            supply_point_default=supply_point,
        )
    ]

    if meter.is_general and not meter.sub_meters.exists():
        try:
            active_sp_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
            active_sp_status = SupplyPointStatus.objects.get(token=active_sp_token)
        except (ConfigProject.DoesNotExist, SupplyPointStatus.DoesNotExist):
            active_sp_status = None
        if active_sp_status is not None:
            seen_contracts = {contract.id for _, contract in targets}
            for sp, contract in _get_general_meter_fanout_targets(
                meter, active_sp_status, contract_active_token
            ):
                if contract.id not in seen_contracts:
                    seen_contracts.add(contract.id)
                    targets.append((sp, contract))

    if not targets:
        targets = [(supply_point, None)]
    return targets


def process_sync_reading_row(
    r, reading_batch, operator, contract_active_token, dry_run=False, only_create=False
):
    """
    Process one reading payload dict (same shape as sync_readings JSON item).

    Returns:
        (action, meter_id, message) where action is 'created', 'updated', or 'skipped'.
    """
    from billing.models import ReaderAlert, Reading
    from service.models import Meter, SupplyPoint, SupplyPointPlacement

    meter_id = r.get('id')
    if not meter_id:
        return 'skipped', None, 'Skipping reading - no meter ID provided'

    try:
        meter = Meter.objects.get(id=int(meter_id))
    except Meter.DoesNotExist:
        return 'skipped', None, f'Meter with ID {meter_id} not found'

    changes_raw = r.get('changes_to_save') or ''
    fields_to_update = [f.strip() for f in changes_raw.split(',') if f.strip()]

    if r.get('previous_reading_id'):
        try:
            previous_reading = Reading.objects.get(id=int(r.get('previous_reading_id')))
        except Reading.DoesNotExist:
            previous_reading = None
    else:
        previous_reading = None

    reading_date = datetime.now().date()

    if 'new_reading_date' in fields_to_update:
        reading_date_str = r.get('new_reading_date')
        if reading_date_str:
            try:
                if isinstance(reading_date_str, datetime):
                    reading_date = reading_date_str.date()
                elif 'T' in str(reading_date_str):
                    reading_datetime = datetime.fromisoformat(
                        str(reading_date_str).replace('Z', '+00:00')
                    )
                    reading_date = reading_datetime.date()
                else:
                    reading_date = datetime.strptime(str(reading_date_str), '%Y-%m-%d').date()
            except ValueError:
                pass

    if previous_reading:
        try:
            can_enter_readings = check_billing_period(
                reading_date=reading_date,
                supply_point=meter.supply_points.filter(token=r.get('supply_token')).first(),
                meter=meter,
                contract=meter.supply_points.filter(token=r.get('supply_token')).first().contracts.filter(token=r.get('contract_token')).first(),
                previous_reading=previous_reading,
                is_termination=False,
            )
            if not can_enter_readings and not previous_reading.billing_id and not _is_meter_change_reading(previous_reading):
                if previous_reading.batch != reading_batch:
                    previous_previous_reading = previous_reading.previous_reading
                    if previous_previous_reading:
                        previous_reading.is_control = True
                        if not dry_run:
                            previous_reading.save()
                        previous_reading = previous_previous_reading
        except Exception as e:
            print(f"Error getting previous reading: {e}")

    # Prefer the original reading: copies (copied_from) are updated through it
    existing_reading = (
        Reading.objects.filter(batch=reading_batch, meter=meter, copied_from__isnull=True).order_by('id').first()
        or Reading.objects.filter(batch=reading_batch, meter=meter).order_by('id').first()
    )

    new_reading_value = _to_float(r.get('new_reading'))
    last_reading_fallback = _to_float(r.get('last_reading'))
    calculated_value = _calculate_value(new_reading_value, previous_reading, last_reading_fallback)

    reading_data = {
        'batch': reading_batch,
        'meter': meter,
        'operator': operator,
        'previous_reading': previous_reading,
        'calculated_value': calculated_value,
        'origin': 'lecturapp',
    }

    if 'new_reading_date' in fields_to_update:
        reading_data['reading_date'] = reading_date

    if 'new_reading' in fields_to_update:
        reading_value = r.get('new_reading')
        if reading_value is not None:
            try:
                reading_data['reading_value'] = float(reading_value)
            except (ValueError, TypeError):
                return 'skipped', meter_id, f'Invalid reading value: {reading_value}'

    if 'reader_alert' in fields_to_update:
        reader_alert_data = r.get('reader_alert')
        if isinstance(reader_alert_data, dict):
            alert_name = reader_alert_data.get('name')
        else:
            alert_name = reader_alert_data
        if alert_name:
            if dry_run:
                reader_alert = ReaderAlert.objects.filter(name=alert_name).first()
            else:
                reader_alert, _ = ReaderAlert.objects.get_or_create(
                    name=alert_name,
                    defaults={'token': alert_name},
                )
            reading_data['reader_alert'] = reader_alert

    if 'new_photo' in fields_to_update:
        photo_data = r.get('new_photo')
        if photo_data:
            try:
                if isinstance(photo_data, str) and photo_data.startswith('data:image'):
                    photo_data = photo_data.split(',')[1]
                image_data = base64.b64decode(photo_data)
                image_file = ContentFile(
                    image_data,
                    name=f"reading_{meter_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                )
                reading_data['photo'] = image_file
            except Exception as exc:
                logger.warning('Error processing photo for meter %s: %s', meter_id, exc)
        else:
            reading_data['photo'] = None

    if not dry_run and (
        'cluster_nozzle_col' in fields_to_update or 'cluster_nozzle_row' in fields_to_update
    ):
        supply_point = SupplyPoint.objects.filter(meter=meter).first()
        if supply_point and supply_point.cluster_nozzle:
            cluster_nozzle = supply_point.cluster_nozzle
            if 'cluster_nozzle_col' in fields_to_update:
                cluster_nozzle.col = r.get('cluster_nozzle_col')
            if 'cluster_nozzle_row' in fields_to_update:
                cluster_nozzle.row = r.get('cluster_nozzle_row')
            cluster_nozzle.save()

    if not dry_run and 'supply_placement' in fields_to_update:
        supply_placement_id = r.get('supply_placement_id')
        if supply_placement_id:
            supply_placement = SupplyPointPlacement.objects.get(id=int(supply_placement_id))
            supply_point = SupplyPoint.objects.filter(meter=meter).first()
            if supply_point:
                supply_point.placement = supply_placement
                supply_point.save()

    if 'reader_observation' in fields_to_update:
        supply_point = None
        supply_token = r.get('supply_token')
        if supply_token:
            supply_point = SupplyPoint.objects.filter(token=supply_token).first()
        if not supply_point:
            supply_point = SupplyPoint.objects.filter(meter=meter).first()
        if supply_point and not dry_run:
            supply_point.reader_observation = r.get('reader_observation') or None
            supply_point.save(update_fields=['reader_observation'])

    if existing_reading:
        if only_create:
            return (
                'skipped',
                meter_id,
                f"Reading already exists in batch {reading_batch.id} for meter {meter_id} (--only-create)",
            )
        if not dry_run:
            reading_data['previous_reading'] = _resolve_previous_reading(
                contract=existing_reading.contract,
                supply_point=existing_reading.supply_point,
                meter=meter,
                reading_date=reading_date,
                reading_batch=reading_batch,
                client_previous_reading=previous_reading,
                dry_run=dry_run,
                exclude_reading_id=existing_reading.id,
            )
            reading_data['calculated_value'] = _calculate_value(
                new_reading_value, reading_data['previous_reading'], last_reading_fallback
            )
            for field, value in reading_data.items():
                if field != 'photo':
                    setattr(existing_reading, field, value)
            if 'photo' in reading_data:
                existing_reading.photo = reading_data['photo']
            existing_reading.save()

            # Keep the copies of this reading (other contracts sharing the meter)
            # in sync, each with its own previous reading
            for copy in existing_reading.copies.filter(batch=reading_batch):
                copy_data = {k: v for k, v in reading_data.items() if k != 'photo'}
                copy_data['previous_reading'] = _resolve_previous_reading(
                    contract=copy.contract,
                    supply_point=copy.supply_point,
                    meter=meter,
                    reading_date=copy_data.get('reading_date', copy.reading_date),
                    reading_batch=reading_batch,
                    client_previous_reading=None,
                    dry_run=dry_run,
                    exclude_reading_id=copy.id,
                )
                copy_data['calculated_value'] = _calculate_value(
                    new_reading_value, copy_data['previous_reading'], last_reading_fallback
                )
                for field, value in copy_data.items():
                    setattr(copy, field, value)
                copy.save()
        return 'updated', meter_id, f"{'[DRY-RUN] Would update' if dry_run else 'Updated'} reading for meter {meter_id}"

    if 'new_reading_date' not in fields_to_update:
        return 'skipped', meter_id, f'No existing reading and new_reading_date not in changes_to_save for meter {meter_id}'

    supply_token = r.get('supply_token')
    if not supply_token:
        supply_point = SupplyPoint.objects.filter(meter=meter).first()
        if not supply_point:
            return 'skipped', meter_id, f'No supply_token and no supply point for meter {meter_id}'
        supply_token = supply_point.token

    try:
        supply_point = SupplyPoint.objects.get(token=supply_token)
    except SupplyPoint.DoesNotExist:
        supply_point = SupplyPoint.objects.filter(meter=meter).first()

    targets = _get_reading_targets(meter, supply_point, contract_active_token)

    contract_count = len(targets)
    original_id = None
    for i, (target_supply_point, contract) in enumerate(targets):
        row_data = dict(reading_data)
        row_data['contract'] = contract
        row_data['previous_reading'] = _resolve_previous_reading(
            contract=contract,
            supply_point=target_supply_point,
            meter=meter,
            reading_date=reading_date,
            reading_batch=reading_batch,
            # The app's previous reading belongs to the supply point it sent
            client_previous_reading=previous_reading if target_supply_point == supply_point else None,
            dry_run=dry_run,
        )
        row_data['calculated_value'] = _calculate_value(
            new_reading_value, row_data['previous_reading'], last_reading_fallback
        )
        row_data['supply_point'] = target_supply_point
        if contract_count > 1 and i > 0 and original_id:
            row_data['copied_from_id'] = original_id
            row_data['token'] = f"{meter.code}/{reading_batch.token}/{i}"
        else:
            row_data['token'] = f"{meter.code}/{reading_batch.token}"

        if dry_run:
            continue

        new_reading = Reading.objects.create(**row_data)
        original_id = original_id if original_id else new_reading.id

    if contract_count == 1 and targets[0][1] is None:
        detail = 'without contract'
    else:
        detail = f'{contract_count} contract(s)'

    return (
        'created',
        meter_id,
        f"{'[DRY-RUN] Would create' if dry_run else 'Created'} reading(s) for meter {meter_id} ({detail})",
    )


def csv_row_to_sync_payload(row):
    """Map lecturapp meter export (or reading logs) CSV row to sync_readings payload."""
    payload = dict(row)

    if not payload.get('id') and payload.get('meter_id'):
        payload['id'] = payload['meter_id']
    if not payload.get('code') and payload.get('meter_code'):
        payload['code'] = payload['meter_code']

    if 'changes_to_save' not in row:
        fields = []
        if payload.get('new_reading') not in (None, ''):
            fields.append('new_reading')
        if payload.get('new_reading_date') not in (None, ''):
            fields.append('new_reading_date')
        if payload.get('new_photo') not in (None, ''):
            fields.append('new_photo')
        if payload.get('reader_alert') not in (None, ''):
            fields.append('reader_alert')
        payload['changes_to_save'] = ','.join(fields)

    if not payload.get('supply_token') and payload.get('id'):
        from service.models import Meter, SupplyPoint

        try:
            meter = Meter.objects.get(id=int(payload['id']))
            supply_point = SupplyPoint.objects.filter(meter=meter).first()
            if supply_point:
                payload['supply_token'] = supply_point.token
        except Meter.DoesNotExist:
            pass

    return payload


def read_csv_file(file_path):
    max_int = sys.maxsize
    while True:
        try:
            csv.field_size_limit(max_int)
            break
        except OverflowError:
            max_int = int(max_int / 10)

    rows = []
    with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',')
        for row in reader:
            rows.append({k: (v if v else None) for k, v in row.items()})
    return rows


def _get_reading_batch(batch_cache, row_batch_id):
    from billing.models import ReadingBatch

    if row_batch_id not in batch_cache:
        batch_cache[row_batch_id] = ReadingBatch.objects.get(id=row_batch_id)
    return batch_cache[row_batch_id]


def load_lecturapp_meter_export(
    file_path,
    operator=None,
    dry_run=False,
    require_changes_to_save=True,
    only_create=False,
):
    """
    Load a lecturapp meters_export (or reading_logs) CSV using sync_readings logic.
    Each row must include reading_batch_id; that batch is used for the reading.

    Returns summary dict: created, updated, skipped, errors (lists of strings).
    """
    from billing.models import ReadingBatch
    from coredata.models import ConfigProject
    from lecturapp.models import ReadingOperator

    if operator is None:
        operator = ReadingOperator.objects.filter(is_active=True).first()
    contract_active_token = ConfigProject.objects.get(token='contract_active_token').value

    rows = read_csv_file(file_path)
    results = {'created': [], 'updated': [], 'skipped': [], 'errors': []}
    batch_cache = {}

    for i, row in enumerate(rows, 1):
        try:
            row_batch_id = int(row['reading_batch_id']) if row.get('reading_batch_id') else None
        except (TypeError, ValueError):
            row_batch_id = None

        if row_batch_id is None:
            results['skipped'].append(f"Row {i}: missing reading_batch_id")
            continue

        changes_to_save = row.get('changes_to_save') or ''
        if require_changes_to_save and changes_to_save == '' and 'changes_to_save' in row:
            results['skipped'].append(f"Row {i}: empty changes_to_save")
            continue

        try:
            reading_batch = _get_reading_batch(batch_cache, row_batch_id)
        except ReadingBatch.DoesNotExist:
            results['errors'].append(f"Row {i}: ReadingBatch {row_batch_id} not found")
            continue

        try:
            payload = csv_row_to_sync_payload(row)
            if require_changes_to_save and not (payload.get('changes_to_save') or '').strip():
                results['skipped'].append(f"Row {i}: nothing to sync")
                continue

            action, meter_id, message = process_sync_reading_row(
                payload,
                reading_batch,
                operator,
                contract_active_token,
                dry_run=dry_run,
                only_create=only_create,
            )
            entry = f"Row {i} (batch {row_batch_id}, meter {meter_id}): {message}"
            if action == 'created':
                results['created'].append(entry)
            elif action == 'updated':
                results['updated'].append(entry)
            else:
                results['skipped'].append(entry)
        except Exception as exc:
            logger.exception('Error processing CSV row %s', i)
            results['errors'].append(f"Row {i}: {exc}")

    return results