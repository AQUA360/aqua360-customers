from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from watchdog.persons_without_contact import (
    format_person_label,
    get_zombie_persons_queryset,
    person_ids_with_bank_in_use,
)


class Command(BaseCommand):
    help = (
        "Elimina persones zombi: sense contacte, ni adreça, ni cap contracte "
        "(titular, propietari, llogater o representant). "
        "No esborra les que tenen un compte bancari encara referenciat. "
        "Recomanat quan el watchdog detecta "
        "'Persones sense contacte ni adreça ni cap contracte'."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra què s'esborraria sense desar canvis",
        )
        parser.add_argument(
            "--id",
            type=str,
            default=None,
            help="Només esborra aquests IDs si continuen sent zombis (separats per comes)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        person_ids = self._parse_ids(options["id"])

        queryset = get_zombie_persons_queryset()
        if person_ids is not None:
            queryset = queryset.filter(id__in=person_ids)
            found_ids = set(queryset.values_list("id", flat=True))
            missing_ids = sorted(set(person_ids) - found_ids)
            if missing_ids:
                self.stdout.write(
                    self.style.WARNING(
                        "IDs no trobats com a persones zombi: "
                        + ", ".join(map(str, missing_ids))
                    )
                )

        persons = list(queryset)
        if not persons:
            self.stdout.write(self.style.SUCCESS("No hi ha persones zombi per eliminar."))
            return

        blocked_ids = person_ids_with_bank_in_use([person.id for person in persons])
        blocked = [person for person in persons if person.id in blocked_ids]
        deletable = [person for person in persons if person.id not in blocked_ids]

        prefix = "[DRY RUN] " if dry_run else ""
        if deletable:
            self.stdout.write(f"{prefix}S'esborrarien {len(deletable)} persones zombi:\n")
            for person in deletable:
                self.stdout.write(f"  - {format_person_label(person)}")

        if blocked:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"{prefix}No s'esborren {len(blocked)} persones perquè el seu "
                    "compte bancari el fa servir un contracte, una factura, un pagament "
                    "o un canvi de dades:"
                )
            )
            for person in blocked:
                self.stdout.write(f"  - {format_person_label(person)}")

        if dry_run or not deletable:
            if deletable:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n{prefix}{len(deletable)} persones zombi pendents d'eliminar."
                    )
                )
            return

        deletable_ids = [person.id for person in deletable]
        with transaction.atomic():
            refresh = get_zombie_persons_queryset().filter(id__in=deletable_ids)
            still_blocked = person_ids_with_bank_in_use(
                list(refresh.values_list("id", flat=True))
            )
            refresh = refresh.exclude(id__in=still_blocked)
            person_count = refresh.count()
            deleted_count, _details = refresh.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nEliminades {person_count} persones zombi "
                f"({deleted_count} files en total, incloent-hi registres en cascada)."
            )
        )
        if still_blocked:
            self.stdout.write(
                self.style.WARNING(
                    "No eliminades perquè el compte bancari ha quedat en ús: "
                    + ", ".join(map(str, sorted(still_blocked)))
                )
            )

    def _parse_ids(self, ids_input):
        if not ids_input:
            return None
        ids = []
        for raw_id in ids_input.split(","):
            raw_id = raw_id.strip()
            if not raw_id:
                continue
            if not raw_id.isdigit():
                raise CommandError(f"ID invàlid: {raw_id}")
            ids.append(int(raw_id))
        if not ids:
            raise CommandError("No s'han proporcionat IDs vàlids")
        return ids
