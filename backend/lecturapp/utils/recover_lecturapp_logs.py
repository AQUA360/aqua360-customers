#!/usr/bin/env python
"""
Recover readings from a lecturapp reading-logs CSV export.

CSV columns: id, meter_id, meter_code, new_reading, new_reading_date, created_at

For each row, skip if the meter already has a reading with the same date OR the same
reading_value. Otherwise create a Reading on the meter's supply point with its active contract.

Usage:
    python manage.py recover_lecturapp_logs path/to/reading_logs_export.csv --dry-run
    python lecturapp/utils/recover_lecturapp_logs.py path/to/file.csv --dry-run
    python manage.py shell
    >>> from lecturapp.utils.recover_lecturapp_logs import recover_lecturapp_logs
    >>> recover_lecturapp_logs('path/to/reading_logs_export.csv')
"""

import argparse
import csv
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger(__name__)

ORIGIN = 'lecturapp-recover'


def _setup_django():
    script_path = os.path.abspath(__file__)
    project_dir = os.path.dirname(script_path)
    while project_dir != os.path.dirname(project_dir):
        if os.path.exists(os.path.join(project_dir, 'manage.py')):
            break
        project_dir = os.path.dirname(project_dir)

    if not os.path.exists(os.path.join(project_dir, 'manage.py')):
        print('Error: Could not find project root (manage.py).')
        sys.exit(1)

    sys.path.insert(0, project_dir)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'customers.settings')
    import django
    django.setup()


def parse_reading_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    value = str(value).strip()
    if 'T' in value:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'Unsupported date format: {value}')


def get_meter(row):
    from service.models import Meter

    meter_id = row.get('meter_id')
    if meter_id:
        try:
            return Meter.objects.get(id=int(meter_id), is_active=True)
        except (Meter.DoesNotExist, ValueError, TypeError):
            pass

    meter_code = (row.get('meter_code') or '').strip()
    if not meter_code:
        return None

    from django.db.models import Q
    return (
        Meter.objects.filter(is_active=True)
        .filter(Q(token=meter_code) | Q(code=meter_code))
        .first()
    )


def reading_already_exists(meter, reading_date, reading_value):
    from django.db.models import Q
    from billing.models import Reading

    if reading_date is None and reading_value is None:
        return False

    qs = Reading.objects.filter(meter=meter, is_active=True)
    conditions = Q()
    if reading_date is not None:
        conditions |= Q(reading_date=reading_date)
    if reading_value is not None:
        conditions |= Q(reading_value=reading_value)
    return qs.filter(conditions).exists()


def get_supply_point_and_contract(meter):
    from django.db.models import Q
    from contract.models import Contract
    from coredata.models import ConfigProject
    from service.models import SupplyPoint

    supply_point = SupplyPoint.objects.filter(meter=meter, is_active=True).order_by('id').first()
    if not supply_point:
        return None, None

    contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
    contract = (
        Contract.objects.filter(
            Q(supply_point_default=supply_point) | Q(supply_points=supply_point),
            is_active=True,
            status__token=contract_active_token,
        )
        .distinct()
        .order_by('id')
        .first()
    )
    return supply_point, contract


def process_row(row, dry_run=False):
    from billing.models import Reading
    from coredata.utils.name_utils import generate_token

    meter = get_meter(row)
    if not meter:
        return 'skipped', f"Meter not found for row id={row.get('id')}"

    try:
        reading_date = parse_reading_date(row.get('new_reading_date'))
    except ValueError as exc:
        return 'error', f"Row id={row.get('id')}: {exc}"

    reading_value_raw = row.get('new_reading')
    if reading_value_raw is None or str(reading_value_raw).strip() == '':
        return 'skipped', f"Row id={row.get('id')}: missing new_reading"

    reading_value = Decimal(str(reading_value_raw))

    if reading_already_exists(meter, reading_date, reading_value):
        return 'skipped', (
            f"Row id={row.get('id')}: duplicate for meter {meter.code} "
            f"(date={reading_date} or value={reading_value})"
        )

    supply_point, contract = get_supply_point_and_contract(meter)
    if not supply_point:
        return 'error', f"Row id={row.get('id')}: no active supply point for meter {meter.code}"
    if not contract:
        return 'error', (
            f"Row id={row.get('id')}: no active contract for supply point {supply_point.token}"
        )

    previous_reading = (
        Reading.objects.filter(
            meter=meter,
            supply_point=supply_point,
            contract=contract,
            reading_date__lt=reading_date,
            is_active=True,
        )
        .exclude(is_control=True)
        .order_by('-reading_date')
        .first()
    )

    if previous_reading and previous_reading.reading_value is not None:
        calculated_value = reading_value - previous_reading.reading_value
        consumption_days = (reading_date - previous_reading.reading_date).days
    else:
        calculated_value = reading_value
        consumption_days = None

    reading_data = {
        'token': generate_token(Reading, '-id', 'LECTURAPP-RECOVER'),
        'contract': contract,
        'supply_point': supply_point,
        'meter': meter,
        'reading_date': reading_date,
        'reading_value': reading_value,
        'calculated_value': calculated_value,
        'consumption_days': consumption_days,
        'previous_reading': previous_reading,
        'origin': ORIGIN,
        'is_active': True,
    }

    if dry_run:
        return 'created', (
            f"[DRY-RUN] Would create reading for meter {meter.code}, "
            f"contract {contract.token}, date {reading_date}, value {reading_value}"
        )

    reading = Reading.objects.create(**reading_data)
    return 'created', (
        f"Created reading id={reading.id} for meter {meter.code}, "
        f"contract {contract.token}, date {reading_date}, value {reading_value}"
    )


def read_csv_file(file_path):
    rows = []
    with open(file_path, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',')
        for row in reader:
            rows.append({k: (v if v else None) for k, v in row.items()})
    return rows


def recover_lecturapp_logs(file_path, dry_run=False):
    """
    Process a lecturapp reading-logs CSV and create missing readings.

    Returns dict with keys: created, skipped, errors (lists of message strings).
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f'File not found: {file_path}')

    rows = read_csv_file(file_path)
    results = {'created': [], 'skipped': [], 'errors': []}

    for row in rows:
        try:
            status, message = process_row(row, dry_run=dry_run)
        except Exception as exc:
            logger.exception('Error processing row %s', row.get('id'))
            results['errors'].append(f"Row id={row.get('id')}: {exc}")
            continue

        if status == 'created':
            results['created'].append(message)
        elif status == 'skipped':
            results['skipped'].append(message)
        else:
            results['errors'].append(message)

    return results


def main():
    parser = argparse.ArgumentParser(description='Recover lecturapp readings from a CSV export.')
    parser.add_argument('csv_path', help='Path to reading_logs_export CSV file')
    parser.add_argument(
        '--dry-run',
        '-n',
        action='store_true',
        help='Report actions without writing to the database',
    )
    args = parser.parse_args()

    if not os.path.isfile(args.csv_path):
        print(f'Error: file not found: {args.csv_path}')
        sys.exit(1)

    _setup_django()

    results = recover_lecturapp_logs(args.csv_path, dry_run=args.dry_run)

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Summary:")
    print(f"  Created: {len(results['created'])}")
    print(f"  Skipped: {len(results['skipped'])}")
    print(f"  Errors:  {len(results['errors'])}")

    for label in ('created', 'skipped', 'errors'):
        if results[label]:
            print(f"\n{label.upper()}:")
            for msg in results[label]:
                print(f"  - {msg}")


if __name__ == '__main__':
    main()
