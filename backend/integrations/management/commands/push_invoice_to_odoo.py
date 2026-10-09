import json
import re
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from billing.models import Invoice
from integrations.outbound.odoo.exceptions import OdooApiError, OdooMappingError
from integrations.outbound.odoo.services import push_invoice


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", value or "").strip("_")
    return cleaned or "invoice"


class Command(BaseCommand):
    help = (
        "Envia factures del PA cap a Odoo, o genera/guarda el JSON amb --dry-run "
        "(per invoice-id o per issue-date)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--invoice-id",
            dest="invoice_id",
            type=int,
            default=None,
            help="ID de billing.Invoice.",
        )
        parser.add_argument(
            "--issue-date",
            dest="issue_date",
            default=None,
            help="Data d'emissió (YYYY-MM-DD) per processar totes les factures d'aquest dia.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Només genera el JSON sense cridar Odoo.",
        )
        parser.add_argument(
            "--output-dir",
            dest="output_dir",
            default="",
            help=(
                "Directori on desar cada payload JSON "
                "(implica --dry-run). Ideal per exemples al proveïdor Odoo."
            ),
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=None,
            help="Màxim de factures a processar (útil amb --issue-date).",
        )

    def handle(self, *args, **options):
        invoice_id = options["invoice_id"]
        issue_date_raw = options["issue_date"]
        output_dir = (options["output_dir"] or "").strip()
        dry_run = options["dry_run"] or bool(output_dir)
        limit = options["limit"]

        if not invoice_id and not issue_date_raw:
            raise CommandError("Cal indicar --invoice-id o --issue-date.")
        if invoice_id and issue_date_raw:
            raise CommandError("Usa només un de --invoice-id o --issue-date.")

        invoice_ids = self._resolve_invoice_ids(invoice_id, issue_date_raw, limit)
        if not invoice_ids:
            raise CommandError("No s'ha trobat cap factura amb els criteris indicats.")

        out_path = None
        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)

        ok = 0
        errors = []
        saved_files = []
        manifest = []

        for pk in invoice_ids:
            try:
                result = push_invoice(pk, dry_run=dry_run)
            except OdooMappingError as exc:
                errors.append((pk, f"mapatge: {exc}"))
                self.stderr.write(self.style.ERROR(f"[{pk}] Error de mapatge: {exc}"))
                continue
            except OdooApiError as exc:
                errors.append((pk, f"api: {exc}"))
                self.stderr.write(self.style.ERROR(f"[{pk}] Error API Odoo: {exc}"))
                continue
            except Invoice.DoesNotExist:
                errors.append((pk, "no trobada"))
                self.stderr.write(self.style.ERROR(f"[{pk}] Factura no trobada."))
                continue

            ok += 1
            aqua_id = result.get("aqua_id", str(pk)) if isinstance(result, dict) else str(pk)

            if dry_run and out_path is not None:
                filename = f"{pk}_{_safe_filename(aqua_id)}.json"
                file_path = out_path / filename
                with file_path.open("w", encoding="utf-8") as fh:
                    json.dump(result, fh, ensure_ascii=False, indent=2)
                    fh.write("\n")
                saved_files.append(str(file_path))
                manifest.append(
                    {
                        "invoice_id": pk,
                        "aqua_id": aqua_id,
                        "name": result.get("name"),
                        "file": filename,
                        "move_type": result.get("move_type"),
                        "amount_total": result.get("amount_total"),
                    }
                )
                self.stdout.write(f"Guardat: {file_path}")
            elif dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"--- invoice_id={pk} ---\n"
                        f"{json.dumps(result, ensure_ascii=False, indent=2)}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Factura {pk} enviada a Odoo: "
                        f"{json.dumps(result, ensure_ascii=False)}"
                    )
                )

        if out_path is not None and manifest:
            manifest_path = out_path / "manifest.json"
            with manifest_path.open("w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "issue_date": issue_date_raw,
                        "dry_run": True,
                        "count": len(manifest),
                        "invoices": manifest,
                    },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )
                fh.write("\n")
            self.stdout.write(f"Manifest: {manifest_path}")

        summary = f"Processades OK: {ok}/{len(invoice_ids)}"
        if errors:
            summary += f" | Errors: {len(errors)}"
            self.stdout.write(self.style.WARNING(summary))
            raise CommandError(
                f"Han fallat {len(errors)} factura(es). "
                "Revisa els errors anteriors."
            )

        self.stdout.write(self.style.SUCCESS(summary))
        if saved_files:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(saved_files)} JSON desats a {out_path.resolve()}"
                )
            )

    def _resolve_invoice_ids(self, invoice_id, issue_date_raw, limit):
        # Pressupost: type_final diferent de 'F'. Prefactura: status_id = 1.
        if invoice_id:
            row = (
                Invoice.objects.filter(pk=invoice_id)
                .values_list("id", "type_final", "status_id")
                .first()
            )
            if row is None:
                return [invoice_id]
            type_final = row[1]
            status_id = row[2]
            if type_final != "F" or status_id == 1:
                raise CommandError(
                    f"L'id {invoice_id} no és una factura "
                    f"(type_final={type_final!r}, status_id={status_id}). "
                    "Només s'envien documents amb type_final='F' i status_id diferent de 1."
                )
            return [invoice_id]

        try:
            issue_date = datetime.strptime(issue_date_raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(
                f"Format de --issue-date invàlid ({issue_date_raw}). Usa YYYY-MM-DD."
            ) from exc

        qs = (
            Invoice.objects.filter(issue_date=issue_date, type_final="F").exclude(
                status_id=1
            )
            .order_by("id")
            .values_list("id", flat=True)
        )
        if limit is not None:
            qs = qs[:limit]
        return list(qs)
