from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Reading


def resolve_reading_supply_point(reading):
    """
    Resol el punt de subministrament d'una lectura:
    primer reading.supply_point, sinó contract.supply_point_default.
    """
    if reading.supply_point_id:
        return reading.supply_point
    if reading.contract_id and reading.contract.supply_point_default_id:
        return reading.contract.supply_point_default
    return None


class Command(BaseCommand):
    help = (
        "Corregeix lectures actives sense meter_id. Per cada lectura, consulta el punt de "
        "subministrament (reading.supply_point o contract.supply_point_default): si té comptador, "
        "l'associa a la lectura; si no en té, marca la lectura com a control (is_control=True). "
        "Recomanat quan el watchdog detecta 'Lectures sense Comptador (meter_id)'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostra què es faria sense desar canvis',
        )
        parser.add_argument(
            '--reading-id',
            type=str,
            default='',
            help='ID(s) de lectura a processar, separats per comes (opcional)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        reading_ids_raw = (options.get('reading_id') or '').strip()

        queryset = Reading.objects.filter(
            is_active=True,
            is_control=False,
            meter__isnull=True,
        ).select_related(
            'contract',
            'contract__supply_point_default',
            'supply_point',
            'supply_point__meter',
        ).order_by('id')

        if reading_ids_raw:
            id_list = []
            for raw_id in reading_ids_raw.split(','):
                raw_id = raw_id.strip()
                if not raw_id:
                    continue
                if not raw_id.isdigit():
                    self.stdout.write(self.style.ERROR(f'ID de lectura no vàlid: {raw_id}'))
                    return
                id_list.append(int(raw_id))
            queryset = queryset.filter(id__in=id_list)

        total = queryset.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No hi ha lectures sense meter_id per processar'))
            return

        self.stdout.write(f'Lectures a processar: {total}')

        assigned_meter = 0
        set_control = 0
        skipped_no_supply_point = 0

        with transaction.atomic():
            for reading in queryset.iterator(chunk_size=200):
                supply_point = resolve_reading_supply_point(reading)

                if not supply_point:
                    skipped_no_supply_point += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'Lectura ID {reading.id}: sense punt de subministrament resoluble, s\'omet'
                        )
                    )
                    continue

                if supply_point.meter_id:
                    assigned_meter += 1
                    action = (
                        f'Lectura ID {reading.id}: assignar meter_id={supply_point.meter_id} '
                        f'(SupplyPoint ID {supply_point.id})'
                    )
                    if dry_run:
                        self.stdout.write(f'[DRY RUN] {action}')
                    else:
                        reading.meter_id = supply_point.meter_id
                        reading.save(update_fields=['meter_id', 'updated_at'])
                        self.stdout.write(action)
                else:
                    set_control += 1
                    action = (
                        f'Lectura ID {reading.id}: marcar is_control=True '
                        f'(SupplyPoint ID {supply_point.id} sense comptador)'
                    )
                    if dry_run:
                        self.stdout.write(f'[DRY RUN] {action}')
                    else:
                        reading.is_control = True
                        reading.save(update_fields=['is_control', 'updated_at'])
                        self.stdout.write(action)

            if dry_run:
                transaction.set_rollback(True)

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'{prefix}Comptador assignat: {assigned_meter}'))
        self.stdout.write(self.style.SUCCESS(f'{prefix}Marcades com a control: {set_control}'))
        if skipped_no_supply_point:
            self.stdout.write(
                self.style.WARNING(
                    f'{prefix}Omeses (sense supply point): {skipped_no_supply_point}'
                )
            )
