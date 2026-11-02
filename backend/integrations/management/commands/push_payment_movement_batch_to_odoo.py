import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from billing.models import Billing, PaymentMovement
from integrations.outbound.odoo.exceptions import OdooApiError, OdooMappingError
from integrations.outbound.odoo.services import push_payment_movement_batch


class Command(BaseCommand):
    help = (
        "Envia un lot de moviments de pagament a Odoo (bulk ≤1000) creant SendBatch, "
        "o genera el JSON del lot amb --dry-run. "
        "Amb --no-send crea SendBatch sense fer POST a Odoo. "
        "Accepta --movement-ids i/o --billing-id / --remittance-id / "
        "--movement-date / --timestamp-date / --invoice-issue-date."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--billing-id",
            dest="billing_id",
            type=int,
            default=None,
            help=(
                "ID de billing.Billing. Filtra moviments via factura "
                "(payment.invoice o payoff_invoice)."
            ),
        )
        parser.add_argument(
            "--movement-ids",
            dest="movement_ids",
            default="",
            help="Llista d'IDs de PaymentMovement separats per comes (p.ex. 10,11,12).",
        )
        parser.add_argument(
            "--movement-date",
            dest="movement_date",
            default=None,
            help="Data del moviment (YYYY-MM-DD) — camp movement_date.",
        )
        parser.add_argument(
            "--timestamp-date",
            dest="timestamp_date",
            default=None,
            help=(
                "Dia del timestamp del moviment (YYYY-MM-DD). "
                "Filtra per PaymentMovement.timestamp (data de creació), "
                "no per movement_date."
            ),
        )
        parser.add_argument(
            "--invoice-issue-date",
            dest="invoice_issue_date",
            default=None,
            help="Data d'emissió de la factura associada (YYYY-MM-DD).",
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
            help="Només genera el JSON del lot sense cridar Odoo ni crear SendBatch.",
        )
        parser.add_argument(
            "--no-send",
            action="store_true",
            help="Crea SendBatch i relaciona moviments, però no fa POST a l'endpoint d'Odoo.",
        )
        parser.add_argument(
            "--output-dir",
            dest="output_dir",
            default="",
            help="Directori on desar el JSON del lot (implica --dry-run).",
        )
        parser.add_argument(
            "--limit",
            dest="limit",
            type=int,
            default=None,
            help="Màxim de moviments.",
        )

    def handle(self, *args, **options):
        billing_id = options["billing_id"]
        movement_ids_raw = (options["movement_ids"] or "").strip()
        movement_date_raw = options["movement_date"]
        timestamp_date_raw = options["timestamp_date"]
        invoice_issue_date_raw = options["invoice_issue_date"]
        remittance_id = options["remittance_id"]
        output_dir = (options["output_dir"] or "").strip()
        dry_run = options["dry_run"] or bool(output_dir)
        no_send = options["no_send"]
        limit = options["limit"]

        has_filter = any(
            [
                billing_id,
                movement_ids_raw,
                movement_date_raw,
                timestamp_date_raw,
                invoice_issue_date_raw,
                remittance_id,
            ]
        )
        if not has_filter:
            raise CommandError(
                "Cal indicar --movement-ids i/o --billing-id / --remittance-id / "
                "--movement-date / --timestamp-date / --invoice-issue-date."
            )
        if dry_run and no_send:
            raise CommandError("--dry-run i --no-send són incompatibles.")

        billing = None
        if billing_id is not None:
            try:
                billing = Billing.objects.get(pk=billing_id)
            except Billing.DoesNotExist as exc:
                raise CommandError(f"Billing {billing_id} no trobat.") from exc

        movement_ids = self._resolve_movement_ids(
            billing=billing,
            movement_ids_raw=movement_ids_raw,
            movement_date_raw=movement_date_raw,
            timestamp_date_raw=timestamp_date_raw,
            invoice_issue_date_raw=invoice_issue_date_raw,
            remittance_id=remittance_id,
            limit=limit,
        )
        if not movement_ids:
            raise CommandError("No s'ha trobat cap moviment amb els criteris indicats.")

        mode = "dry-run" if dry_run else ("no-send" if no_send else "send")
        self.stdout.write(
            f"Lot: {len(movement_ids)} moviment(s)"
            + (f" | billing_id={billing.id}" if billing else "")
            + (f" | remittance_id={remittance_id}" if remittance_id else "")
            + f" | {mode}"
        )

        try:
            results = push_payment_movement_batch(
                movement_ids,
                billing=billing,
                dry_run=dry_run,
                send=not no_send,
            )
        except OdooMappingError as exc:
            raise CommandError(f"Error de mapatge: {exc}") from exc
        except OdooApiError as exc:
            raise CommandError(f"Error API Odoo: {exc}") from exc

        if dry_run:
            self._handle_dry_run(results, output_dir, billing_id, movement_ids)
            return

        for batch in results:
            self.stdout.write(
                self.style.SUCCESS(
                    f"SendBatch {batch.token} creat "
                    f"(id={batch.id}, http={batch.instant_status_code}, "
                    f"status={batch.status.token if batch.status else None}, "
                    f"payments={batch.payments.count()})"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Lots {'creats (sense enviament)' if no_send else 'enviats'}: {len(results)}"
            )
        )

    def _parse_date(self, raw, flag_name):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(
                f"Format de {flag_name} invàlid ({raw}). Usa YYYY-MM-DD."
            ) from exc

    def _base_queryset(self):
        return PaymentMovement.objects.filter(
            is_active=True, is_positive__isnull=False
        )

    def _apply_filters(
        self,
        qs,
        *,
        billing,
        remittance_id,
        movement_date_raw,
        timestamp_date_raw,
        invoice_issue_date_raw,
    ):
        if billing is not None:
            qs = qs.filter(
                Q(payment__invoice__billing=billing)
                | Q(payoff_invoice__billing=billing)
            )
        if remittance_id is not None:
            qs = qs.filter(payment_remittance_id=remittance_id)
        if movement_date_raw:
            qs = qs.filter(
                movement_date=self._parse_date(movement_date_raw, "--movement-date")
            )
        if timestamp_date_raw:
            # Filtra pel dia civil de PaymentMovement.timestamp (DateTimeField).
            qs = qs.filter(
                timestamp__date=self._parse_date(
                    timestamp_date_raw, "--timestamp-date"
                )
            )
        if invoice_issue_date_raw:
            issue_date = self._parse_date(
                invoice_issue_date_raw, "--invoice-issue-date"
            )
            qs = qs.filter(
                Q(payment__invoice__issue_date=issue_date)
                | Q(payoff_invoice__issue_date=issue_date)
            )
        return qs

    def _resolve_movement_ids(
        self,
        *,
        billing,
        movement_ids_raw,
        movement_date_raw,
        timestamp_date_raw,
        invoice_issue_date_raw,
        remittance_id,
        limit,
    ):
        if movement_ids_raw:
            try:
                ids = [
                    int(part.strip())
                    for part in movement_ids_raw.split(",")
                    if part.strip()
                ]
            except ValueError as exc:
                raise CommandError(
                    f"Format de --movement-ids invàlid ({movement_ids_raw}). "
                    "Usa enters separats per comes."
                ) from exc
            if not ids:
                raise CommandError("--movement-ids està buit.")

            qs = self._apply_filters(
                self._base_queryset().filter(pk__in=ids),
                billing=billing,
                remittance_id=remittance_id,
                movement_date_raw=movement_date_raw,
                timestamp_date_raw=timestamp_date_raw,
                invoice_issue_date_raw=invoice_issue_date_raw,
            )

            found = list(qs.order_by("id").values_list("id", flat=True).distinct())
            missing = sorted(set(ids) - set(found))
            if missing:
                raise CommandError(
                    "Moviments no vàlids o no trobats "
                    "(is_active, is_positive informat"
                    + (f", billing_id={billing.id}" if billing else "")
                    + f"): {missing}"
                )
            return found

        qs = self._apply_filters(
            self._base_queryset(),
            billing=billing,
            remittance_id=remittance_id,
            movement_date_raw=movement_date_raw,
            timestamp_date_raw=timestamp_date_raw,
            invoice_issue_date_raw=invoice_issue_date_raw,
        )

        qs = qs.order_by("id").values_list("id", flat=True).distinct()
        if limit is not None:
            qs = qs[:limit]
        return list(qs)

    def _handle_dry_run(self, results, output_dir, billing_id, movement_ids):
        for idx, payload in enumerate(results, start=1):
            rendered = json.dumps(payload, ensure_ascii=False, indent=2)
            if output_dir:
                out_path = Path(output_dir)
                out_path.mkdir(parents=True, exist_ok=True)
                batch_id = payload.get("batch_id") or f"batch-{idx}"
                file_path = out_path / f"{batch_id}.json"
                with file_path.open("w", encoding="utf-8") as fh:
                    fh.write(rendered)
                    fh.write("\n")
                self.stdout.write(f"Guardat: {file_path}")
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"--- lot {idx}/{len(results)} ---\n{rendered}"
                    )
                )

        if output_dir:
            out_path = Path(output_dir)
            manifest_path = out_path / "manifest.json"
            with manifest_path.open("w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "billing_id": billing_id,
                        "dry_run": True,
                        "movement_ids": movement_ids,
                        "batches": [
                            {
                                "batch_id": p.get("batch_id"),
                                "items": len(p.get("items") or []),
                                "file": f"{p.get('batch_id') or f'batch-{i}'}.json",
                            }
                            for i, p in enumerate(results, start=1)
                        ],
                    },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                )
                fh.write("\n")
            self.stdout.write(f"Manifest: {manifest_path}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Dry-run OK: {len(results)} lot(s), {len(movement_ids)} moviment(s)"
            )
        )
