import json
import re
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from billing.models import PaymentMovement
from integrations.outbound.odoo.exceptions import OdooApiError, OdooMappingError
from integrations.outbound.odoo.services import push_payment_movement


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", value or "").strip("_")
    return cleaned or "movement"


class Command(BaseCommand):
    help = (
        "Envia moviments de pagament (billing.PaymentMovement) cap a Odoo, "
        "o genera/guarda el JSON amb --dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--movement-id",
            dest="movement_id",
            type=int,
            default=None,
            help="ID de billing.PaymentMovement.",
        )
        parser.add_argument(
            "--movement-date",
            dest="movement_date",
            default=None,
            help="Data del moviment (YYYY-MM-DD) per processar-ne un lot.",
        )
        parser.add_argument(
            "--invoice-issue-date",
            dest="invoice_issue_date",
            default=None,
            help=(
                "Data d'emissió de la factura associada (YYYY-MM-DD). "
                "Útil després d'una facturació + remesa SEPA."
            ),
        )
        parser.add_argument(
            "--remittance-id",
            dest="remittance_id",
            type=int,
            default=None,
            help="ID de billing.PaymentRemittance.",
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
            help="Màxim de moviments a processar.",
        )

    def handle(self, *args, **options):
        movement_id = options["movement_id"]
        movement_date_raw = options["movement_date"]
        invoice_issue_date_raw = options["invoice_issue_date"]
        remittance_id = options["remittance_id"]
        output_dir = (options["output_dir"] or "").strip()
        dry_run = options["dry_run"] or bool(output_dir)
        limit = options["limit"]

        selectors = [
            bool(movement_id),
            bool(movement_date_raw),
            bool(invoice_issue_date_raw),
            bool(remittance_id),
        ]
        if sum(selectors) != 1:
            raise CommandError(
                "Cal indicar exactament un de: --movement-id, --movement-date, "
                "--invoice-issue-date o --remittance-id."
            )

        movement_ids = self._resolve_movement_ids(
            movement_id=movement_id,
            movement_date_raw=movement_date_raw,
            invoice_issue_date_raw=invoice_issue_date_raw,
            remittance_id=remittance_id,
            limit=limit,
        )
        if not movement_ids:
            raise CommandError("No s'ha trobat cap moviment amb els criteris indicats.")

        out_path = None
        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)

        ok = 0
        errors = []
        saved_files = []
        manifest = []

        for pk in movement_ids:
            try:
                result = push_payment_movement(pk, dry_run=dry_run)
            except OdooMappingError as exc:
                errors.append((pk, f"mapatge: {exc}"))
                self.stderr.write(self.style.ERROR(f"[{pk}] Error de mapatge: {exc}"))
                continue
            except OdooApiError as exc:
                errors.append((pk, f"api: {exc}"))
                self.stderr.write(self.style.ERROR(f"[{pk}] Error API Odoo: {exc}"))
                continue
            except PaymentMovement.DoesNotExist:
                errors.append((pk, "no trobat"))
                self.stderr.write(self.style.ERROR(f"[{pk}] Moviment no trobat."))
                continue

            ok += 1
            aqua_id = (
                result.get("aqua_id", str(pk)) if isinstance(result, dict) else str(pk)
            )

            if dry_run and out_path is not None:
                filename = f"{pk}_{_safe_filename(aqua_id)}.json"
                file_path = out_path / filename
                with file_path.open("w", encoding="utf-8") as fh:
                    json.dump(result, fh, ensure_ascii=False, indent=2)
                    fh.write("\n")
                saved_files.append(str(file_path))
                manifest.append(
                    {
                        "movement_id": pk,
                        "aqua_id": aqua_id,
                        "file": filename,
                        "amount": result.get("amount"),
                        "date": result.get("date"),
                        "invoice_aqua_id": (result.get("reconcile") or {}).get(
                            "invoice_aqua_id"
                        ),
                    }
                )
                self.stdout.write(f"Guardat: {file_path}")
            elif dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"--- movement_id={pk} ---\n"
                        f"{json.dumps(result, ensure_ascii=False, indent=2)}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Moviment {pk} enviat a Odoo: "
                        f"{json.dumps(result, ensure_ascii=False)}"
                    )
                )

        if out_path is not None and manifest:
            manifest_path = out_path / "manifest.json"
            with manifest_path.open("w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "movement_date": movement_date_raw,
                        "invoice_issue_date": invoice_issue_date_raw,
                        "remittance_id": remittance_id,
                        "dry_run": True,
                        "count": len(manifest),
                        "movements": manifest,
                    },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )
                fh.write("\n")
            self.stdout.write(f"Manifest: {manifest_path}")

        summary = f"Processats OK: {ok}/{len(movement_ids)}"
        if errors:
            summary += f" | Errors: {len(errors)}"
            self.stdout.write(self.style.WARNING(summary))
            raise CommandError(
                f"Han fallat {len(errors)} moviment(s). "
                "Revisa els errors anteriors."
            )

        self.stdout.write(self.style.SUCCESS(summary))
        if saved_files:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{len(saved_files)} JSON desats a {out_path.resolve()}"
                )
            )

    def _parse_date(self, raw, flag_name):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(
                f"Format de {flag_name} invàlid ({raw}). Usa YYYY-MM-DD."
            ) from exc

    def _resolve_movement_ids(
        self,
        *,
        movement_id,
        movement_date_raw,
        invoice_issue_date_raw,
        remittance_id,
        limit,
    ):
        if movement_id:
            return [movement_id]

        qs = PaymentMovement.objects.filter(is_active=True, is_positive__isnull=False)

        if movement_date_raw:
            qs = qs.filter(
                movement_date=self._parse_date(movement_date_raw, "--movement-date")
            )
        elif invoice_issue_date_raw:
            issue_date = self._parse_date(
                invoice_issue_date_raw, "--invoice-issue-date"
            )
            qs = qs.filter(
                Q(payment__invoice__issue_date=issue_date)
                | Q(payoff_invoice__issue_date=issue_date)
            )
        elif remittance_id:
            qs = qs.filter(payment_remittance_id=remittance_id)

        qs = qs.order_by("id").values_list("id", flat=True).distinct()
        if limit is not None:
            qs = qs[:limit]
        return list(qs)
