"""
CLI wrapper for load_lecturapp_meter_export (same entry point as the management command).

Usage:
    python lecturapp/utils/load_lecturapp_meter_export.py <csv_path> --dry-run
"""

import argparse
import os
import sys


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


def main():
    parser = argparse.ArgumentParser(description='Load lecturapp meter export CSV (sync_readings logic).')
    parser.add_argument('csv_path', help='Path to meters_export CSV (reading_batch_id per row)')
    parser.add_argument('--operator-id', type=int, default=None)
    parser.add_argument('--dry-run', '-n', action='store_true')
    parser.add_argument(
        '--include-empty-changes',
        action='store_true',
        help='Process rows with empty changes_to_save',
    )
    parser.add_argument(
        '--only-create',
        action='store_true',
        help='Only create new readings; skip updates',
    )
    args = parser.parse_args()

    _setup_django()
    from lecturapp.models import ReadingOperator
    from lecturapp.utils.sync_readings_service import load_lecturapp_meter_export

    operator = None
    if args.operator_id:
        operator = ReadingOperator.objects.get(id=args.operator_id)

    results = load_lecturapp_meter_export(
        args.csv_path,
        operator=operator,
        dry_run=args.dry_run,
        require_changes_to_save=not args.include_empty_changes,
        only_create=args.only_create,
    )

    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}Summary:")
    for key in ('created', 'updated', 'skipped', 'errors'):
        print(f"  {key}: {len(results[key])}")


if __name__ == '__main__':
    main()
