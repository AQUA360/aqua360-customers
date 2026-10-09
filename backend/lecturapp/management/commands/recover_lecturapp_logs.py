from django.core.management.base import BaseCommand, CommandError

from lecturapp.utils.recover_lecturapp_logs import recover_lecturapp_logs


class Command(BaseCommand):
    help = (
        'Recover readings from a lecturapp reading_logs_export CSV. '
        'Skips rows when the meter already has a reading with the same date or value; '
        'otherwise creates a reading on the active contract of the supply point.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            type=str,
            help='Path to reading_logs_export CSV (id, meter_id, meter_code, new_reading, new_reading_date, ...)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report actions without writing to the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no database changes will be made'))

        try:
            results = recover_lecturapp_logs(options['csv_path'], dry_run=dry_run)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(f"Created: {len(results['created'])}")
        self.stdout.write(f"Skipped: {len(results['skipped'])}")
        self.stdout.write(f"Errors:  {len(results['errors'])}")

        for label in ('created', 'skipped', 'errors'):
            items = results[label]
            if not items:
                continue
            self.stdout.write(f"\n{label.upper()}:")
            for msg in items[:50]:
                self.stdout.write(f"  - {msg}")
            if len(items) > 50:
                self.stdout.write(f"  ... and {len(items) - 50} more")

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN — no changes were saved'))
