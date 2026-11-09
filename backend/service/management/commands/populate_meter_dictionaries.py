from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from service.models import Meter, MeterCommTechnology, MeterManufacturer, MeterModel
from service.utils.meter_dictionary_service import (
    get_or_create_dictionary_value,
    normalize_dictionary_name,
)


TARGETS = ('manufacturer', 'model', 'comm_technology')


class Command(BaseCommand):
    help = (
        "Omple els diccionaris de comptadors (fabricants, models i tecnologies de comunicació) "
        "a partir dels valors de text ja informats als comptadors. És idempotent: no crea duplicats "
        "(sense distingir majúscules) i es pot tornar a executar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Mostra què es crearia sense escriure res a la base de dades.",
        )
        parser.add_argument(
            '--only',
            action='append',
            choices=TARGETS,
            help="Limita l'execució a un diccionari (es pot repetir).",
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        targets = options['only'] or list(TARGETS)

        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN: no es desarà cap canvi.'))

        with transaction.atomic():
            if 'manufacturer' in targets:
                self._populate_flat('manufacturer', MeterManufacturer)
            if 'model' in targets:
                self._populate_models()
            if 'comm_technology' in targets:
                self._populate_flat('comm_technology', MeterCommTechnology)
            if self.dry_run:
                transaction.set_rollback(True)

    # -- helpers ---------------------------------------------------------------

    def _distinct_values(self, model, raw_values):
        """
        Normalitza (trim) i deduplica sense distingir majúscules; guanya la primera
        grafia trobada. Retorna (valors, invàlids).
        """
        values = {}
        invalid = 0
        for raw in raw_values:
            if raw is None or not str(raw).strip():
                continue
            try:
                name = normalize_dictionary_name(model, str(raw))
            except ValueError:
                invalid += 1
                continue
            values.setdefault(name.casefold(), name)
        return list(values.values()), invalid

    def _store(self, model, name, stats, **filters):
        # En dry-run també es crea, però dins d'una transacció que es desfà al final:
        # així els models troben el seu fabricant i els recomptes són fidels.
        value, created = get_or_create_dictionary_value(model, name, **filters)
        stats['created' if created else 'existing'] += 1
        return value

    def _report(self, label, found, stats):
        self.stdout.write(self.style.SUCCESS(
            f"{label}: {found} valors trobats, {stats['created']} creats, "
            f"{stats['existing']} ja existents."
        ))
        if stats['invalid']:
            self.stdout.write(self.style.WARNING(
                f"{label}: {stats['invalid']} valors descartats (massa llargs o no vàlids)."
            ))
        if stats['skipped']:
            self.stdout.write(self.style.WARNING(
                f"{label}: {stats['skipped']} combinacions omeses (model sense fabricant)."
            ))

    # -- populators -------------------------------------------------------------

    def _populate_flat(self, field, model):
        raw_values = (
            Meter.objects.exclude(**{f'{field}__isnull': True})
            .exclude(**{field: ''})
            .order_by('id')
            .values_list(field, flat=True)
        )
        values, invalid = self._distinct_values(model, raw_values.iterator())
        stats = Counter(invalid=invalid)
        for name in values:
            self._store(model, name, stats)
        self._report(model._meta.object_name, len(values), stats)

    def _populate_models(self):
        rows = (
            Meter.objects.exclude(model__isnull=True)
            .exclude(model='')
            .order_by('id')
            .values_list('manufacturer', 'model')
        )
        stats = Counter()
        pairs = {}
        for manufacturer_raw, model_raw in rows.iterator():
            if not (model_raw or '').strip():
                continue
            if not (manufacturer_raw or '').strip():
                stats['skipped'] += 1
                continue
            try:
                manufacturer_name = normalize_dictionary_name(MeterManufacturer, manufacturer_raw)
                model_name = normalize_dictionary_name(MeterModel, model_raw)
            except ValueError:
                stats['invalid'] += 1
                continue
            key = (manufacturer_name.casefold(), model_name.casefold())
            pairs.setdefault(key, (manufacturer_name, model_name))

        manufacturers = {}
        manufacturer_stats = Counter()
        for manufacturer_name, model_name in pairs.values():
            key = manufacturer_name.casefold()
            if key not in manufacturers:
                manufacturers[key] = self._store(MeterManufacturer, manufacturer_name, manufacturer_stats)
            self._store(MeterModel, model_name, stats, manufacturer=manufacturers[key])

        if manufacturer_stats['created']:
            self.stdout.write(self.style.SUCCESS(
                f"MeterManufacturer (via models): {manufacturer_stats['created']} creats."
            ))
        self._report('MeterModel', len(pairs), stats)
