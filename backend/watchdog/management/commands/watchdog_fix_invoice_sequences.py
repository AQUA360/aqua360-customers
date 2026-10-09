from django.core.management.base import BaseCommand
from django.db import transaction

from watchdog.services import find_desynced_invoice_sequences


class Command(BaseCommand):
    help = (
        "Sincronitza InvoiceSequence.last_number amb el número màxim ja assignat "
        "a Invoice.serie_final per a cada prefix (p. ex. FC/1826). "
        "Ús després de: python manage.py watchdog sniff"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra què es faria sense desar canvis",
        )
        parser.add_argument(
            "--prefix",
            type=str,
            default="",
            help="Prefix concret a corregir (ex: FC/1826). Sense argument, corregeix tots els desfasats.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        prefix_filter: str = (options.get("prefix") or "").strip()

        desynced = find_desynced_invoice_sequences()
        if prefix_filter:
            desynced = [item for item in desynced if item["prefix"] == prefix_filter]
            if not desynced:
                self.stdout.write(
                    self.style.WARNING(
                        f"No hi ha desfasament per al prefix {prefix_filter!r} "
                        "(o el prefix no existeix / ja està sincronitzat)."
                    )
                )
                return

        if not desynced:
            self.stdout.write(
                self.style.SUCCESS(
                    "Totes les InvoiceSequence de serie_final estan sincronitzades."
                )
            )
            return

        for item in desynced:
            msg = (
                f"'{item['prefix']}': last_number {item['last_number']} -> {item['max_number']} "
                f"(max serie_final={item['max_serie_final']})"
            )
            if dry_run:
                self.stdout.write(f"[dry-run] {msg}")
                continue

            with transaction.atomic():
                seq = item["sequence"]
                seq.last_number = item["max_number"]
                seq.save(update_fields=["last_number"])
            self.stdout.write(self.style.SUCCESS(msg))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(desynced)} seqüència(es) pendents. "
                    "Executa sense --dry-run per aplicar."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"{len(desynced)} seqüència(es) sincronitzada(es).")
            )
