import csv
import sys

from django.core.management.base import BaseCommand, CommandError

from integrations.outbound.giswater.exceptions import GiswaterApiError
from integrations.outbound.giswater.sync import sync_connections_from_giswater

STAT_KEYS = (
    "total_fields",
    "esco_tokens",
    "skipped",
    "updated",
    "not_found",
    "unchanged",
)

NOT_FOUND_CSV_FIELDS = ("customer_code", "code_gis", "latitude", "longitude")


class Command(BaseCommand):
    help = (
        "Sincronitza Connection des de Giswater (ESCO): "
        "code_gis, latitude i longitude per token=customer_code."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-not-found",
            action="store_true",
            help="Mostra només els customer_code sense Connection al PA.",
        )
        parser.add_argument(
            "--csv",
            dest="csv_path",
            default="",
            help="Exporta not_found a CSV. Ruta de fitxer o '-' per stdout.",
        )

    def handle(self, *args, **options):
        try:
            stats = sync_connections_from_giswater()
        except GiswaterApiError as exc:
            raise CommandError(str(exc)) from exc

        csv_path = options["csv_path"]
        only_not_found = options["only_not_found"]

        if csv_path:
            self._export_not_found_csv(stats, csv_path)

        if only_not_found:
            if not csv_path:
                self._print_not_found(stats)
            return

        self.stdout.write(self.style.SUCCESS("Sincronització completada"))
        for key in STAT_KEYS:
            self.stdout.write(f"  {key}: {stats[key]}")

        if not csv_path:
            self._print_not_found(stats)

    def _print_not_found(self, stats):
        not_found_tokens = stats.get("not_found_tokens") or []
        if not not_found_tokens:
            self.stdout.write(self.style.SUCCESS("Cap not_found."))
            return

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"not_found ({len(not_found_tokens)}): customer_code de Giswater "
                "sense Connection activa amb token coincident"
            )
        )
        for item in not_found_tokens:
            self.stdout.write(
                f"  customer_code={item['customer_code']}  "
                f"code_gis={item['code_gis']}  "
                f"lat={item['latitude']}  long={item['longitude']}"
            )

    def _export_not_found_csv(self, stats, csv_path):
        not_found_tokens = stats.get("not_found_tokens") or []

        if csv_path == "-":
            writer = csv.DictWriter(
                sys.stdout, fieldnames=NOT_FOUND_CSV_FIELDS, delimiter=";"
            )
            writer.writeheader()
            for item in not_found_tokens:
                writer.writerow(self._csv_row(item))
            return

        with open(csv_path, "w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file, fieldnames=NOT_FOUND_CSV_FIELDS, delimiter=";"
            )
            writer.writeheader()
            for item in not_found_tokens:
                writer.writerow(self._csv_row(item))

        self.stdout.write(
            self.style.SUCCESS(
                f"CSV not_found exportat ({len(not_found_tokens)} files): {csv_path}"
            )
        )

    def _csv_row(self, item):
        return {
            "customer_code": item["customer_code"],
            "code_gis": item["code_gis"],
            "latitude": item["latitude"] if item["latitude"] is not None else "",
            "longitude": item["longitude"] if item["longitude"] is not None else "",
        }
