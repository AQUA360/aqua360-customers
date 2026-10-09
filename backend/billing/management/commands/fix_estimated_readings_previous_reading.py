from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import Reading


class Command(BaseCommand):
    help = (
        'Assigna previous_reading a les lectures estimades que el tenen a NULL. '
        'Busca la lectura no-control immediament anterior per supply_point + contract. '
        'Executa primer amb --dry-run per previsualitzar els canvis.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra els canvis sense desar-los',
        )
        parser.add_argument(
            '--batch-id',
            type=int,
            help='Limita la correcció a les lectures d\'un lot concret (ID)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Nombre màxim de lectures a processar',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_id = options.get('batch_id')
        limit = options.get('limit')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: no es desaran canvis.'))

        qs = Reading.objects.filter(
            is_estimated=True,
            is_control=False,
            is_active=True,
            previous_reading__isnull=True,
        ).select_related('supply_point', 'contract').order_by('reading_date')

        if batch_id:
            qs = qs.filter(batch__id=batch_id)

        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(f'Lectures estimades sense previous_reading trobades: {total}')

        updated = 0
        skipped = 0

        for reading in qs.iterator():
            prev = (
                Reading.objects.filter(
                    supply_point=reading.supply_point,
                    contract=reading.contract,
                    reading_date__lt=reading.reading_date,
                    is_control=False,
                )
                .order_by('-reading_date')
                .first()
            )

            if not prev:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f'  Reading {reading.id} ({reading.reading_date}) → previous_reading = {prev.id} ({prev.reading_date})'
                )
            else:
                with transaction.atomic():
                    reading.previous_reading = prev
                    reading.save(update_fields=['previous_reading'])

            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'{"[DRY RUN] " if dry_run else ""}Actualitzades: {updated} | Sense anterior: {skipped}'
            )
        )
