from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from watchdog.orphaned_addresses import (
    format_orphaned_address_issue,
    get_orphaned_addresses_queryset,
)


class Command(BaseCommand):
    help = (
        "Elimina adreces orfes (sense relació amb Person, SupplyPoint, Order ni Company). "
        "Recomanat quan el watchdog detecta 'Adreces Orfes'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra què s\'esborraria sense desar canvis',
        )
        parser.add_argument(
            '--id',
            type=str,
            default=None,
            help='Només esborra aquests IDs si continuen sent orfes (separats per comes)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        address_ids = self._parse_ids(options['id'])

        queryset = get_orphaned_addresses_queryset()
        if address_ids is not None:
            queryset = queryset.filter(id__in=address_ids)
            found_ids = set(queryset.values_list('id', flat=True))
            missing_ids = sorted(set(address_ids) - found_ids)
            if missing_ids:
                self.stdout.write(
                    self.style.WARNING(
                        "IDs no trobats com a adreces orfes: "
                        + ", ".join(map(str, missing_ids))
                    )
                )

        addresses = list(queryset)
        if not addresses:
            self.stdout.write(
                self.style.SUCCESS('No hi ha adreces orfes per eliminar.')
            )
            return

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(f"{prefix}S'esborrarien {len(addresses)} adreces orfes:\n")
        for address in addresses:
            self.stdout.write(f"  - {format_orphaned_address_issue(address)}")

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n{prefix}{len(addresses)} adreces orfes pendents d'eliminar."
                )
            )
            return

        with transaction.atomic():
            deleted_count, _details = queryset.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nEliminades {deleted_count} adreces orfes correctament."
            )
        )

    def _parse_ids(self, ids_input):
        if not ids_input:
            return None
        ids = []
        for raw_id in ids_input.split(','):
            raw_id = raw_id.strip()
            if not raw_id:
                continue
            if not raw_id.isdigit():
                raise CommandError(f"ID invàlid: {raw_id}")
            ids.append(int(raw_id))
        if not ids:
            raise CommandError("No s'han proporcionat IDs vàlids")
        return ids
