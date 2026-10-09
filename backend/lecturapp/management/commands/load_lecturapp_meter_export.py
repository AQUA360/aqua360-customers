from django.core.management.base import BaseCommand, CommandError

from lecturapp.models import ReadingOperator
from lecturapp.utils.sync_readings_service import load_lecturapp_meter_export


class Command(BaseCommand):
    help = (
        'Load a lecturapp meters_export CSV using the same logic as sync_readings. '
        'Uses reading_batch_id from each CSV row.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            type=str,
            help='Path to the CSV export file (must include reading_batch_id per row)',
        )
        parser.add_argument(
            '--operator-id',
            type=int,
            default=None,
            help='ReadingOperator ID (default: first active operator)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without writing to the database',
        )
        parser.add_argument(
            '--include-empty-changes',
            action='store_true',
            help='Process rows with empty changes_to_save (meters export rows without edits)',
        )
        parser.add_argument(
            '--only-create',
            action='store_true',
            help='Only create new readings; skip rows that would update an existing batch reading',
        )

    def handle(self, *args, **options):
        operator = None
        if options['operator_id']:
            try:
                operator = ReadingOperator.objects.get(id=options['operator_id'])
            except ReadingOperator.DoesNotExist as exc:
                raise CommandError(f"Operator id={options['operator_id']} not found") from exc
        else:
            operator = ReadingOperator.objects.filter(is_active=True).first()
            if not operator:
                raise CommandError('No active ReadingOperator found. Create one or pass --operator-id.')

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no database changes will be made'))

        try:
            results = load_lecturapp_meter_export(
                options['csv_path'],
                operator=operator,
                dry_run=dry_run,
                require_changes_to_save=not options['include_empty_changes'],
                only_create=options['only_create'],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f"Created: {len(results['created'])}")
        self.stdout.write(f"Updated: {len(results['updated'])}")
        self.stdout.write(f"Skipped: {len(results['skipped'])}")
        self.stdout.write(f"Errors:  {len(results['errors'])}")

        for label in ('created', 'updated', 'skipped', 'errors'):
            items = results[label]
            if not items:
                continue
            self.stdout.write(f"\n{label.upper()}:")
            for msg in items[:50]:
                self.stdout.write(f"  - {msg}")
            if len(items) > 50:
                self.stdout.write(f"  ... and {len(items) - 50} more")
