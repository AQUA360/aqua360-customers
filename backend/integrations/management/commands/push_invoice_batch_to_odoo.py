import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from billing.models import Billing, Invoice
from integrations.outbound.odoo.exceptions import OdooApiError, OdooMappingError
from integrations.outbound.odoo.services import push_invoice_batch


class Command(BaseCommand):
    help = (
        "Envia un lot de factures a Odoo (bulk ≤1000) creant SendBatch, "
        "o genera el JSON del lot amb --dry-run. "
        "Amb --no-send crea SendBatch sense fer POST a Odoo. "
        "Accepta --billing-id i/o --invoice-ids."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--billing-id",
            dest="billing_id",
            type=int,
            default=None,
            help="ID de billing.Billing. Si no hi ha --invoice-ids, envia totes les factures d'aquesta facturació.",
        )
        parser.add_argument(
            "--invoice-ids",
            dest="invoice_ids",
            default="",
            help="Llista d'IDs de factura separats per comes (p.ex. 10,11,12).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Només genera el JSON del lot sense cridar Odoo ni crear SendBatch.",
        )
        parser.add_argument(
            "--no-send",
            action="store_true",
            help="Crea SendBatch i relaciona factures, però no fa POST a l'endpoint d'Odoo.",
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
            help="Màxim de factures (útil amb només --billing-id).",
        )

    def handle(self, *args, **options):
        billing_id = options["billing_id"]
        invoice_ids_raw = (options["invoice_ids"] or "").strip()
        output_dir = (options["output_dir"] or "").strip()
        dry_run = options["dry_run"] or bool(output_dir)
        no_send = options["no_send"]
        limit = options["limit"]

        if not billing_id and not invoice_ids_raw:
            raise CommandError("Cal indicar --billing-id i/o --invoice-ids.")
        if dry_run and no_send:
            raise CommandError("--dry-run i --no-send són incompatibles.")

        billing = None
        if billing_id is not None:
            try:
                billing = Billing.objects.get(pk=billing_id)
            except Billing.DoesNotExist as exc:
                raise CommandError(f"Billing {billing_id} no trobat.") from exc

        invoice_ids = self._resolve_invoice_ids(
            billing=billing,
            invoice_ids_raw=invoice_ids_raw,
            limit=limit,
        )
        if not invoice_ids:
            raise CommandError("No s'ha trobat cap factura amb els criteris indicats.")

        mode = "dry-run" if dry_run else ("no-send" if no_send else "send")
        self.stdout.write(
            f"Lot: {len(invoice_ids)} factura(es)"
            + (f" | billing_id={billing.id}" if billing else "")
            + f" | {mode}"
        )

        try:
            results = push_invoice_batch(
                invoice_ids,
                billing=billing,
                dry_run=dry_run,
                send=not no_send,
            )
        except OdooMappingError as exc:
            raise CommandError(f"Error de mapatge: {exc}") from exc
        except OdooApiError as exc:
            raise CommandError(f"Error API Odoo: {exc}") from exc

        if dry_run:
            self._handle_dry_run(results, output_dir, billing_id, invoice_ids)
            return

        for batch in results:
            self.stdout.write(
                self.style.SUCCESS(
                    f"SendBatch {batch.token} creat "
                    f"(id={batch.id}, http={batch.instant_status_code}, "
                    f"status={batch.status.token if batch.status else None}, "
                    f"invoices={batch.invoices.count()})"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Lots {'creats (sense enviament)' if no_send else 'enviats'}: {len(results)}"
            )
        )

    def _resolve_invoice_ids(self, *, billing, invoice_ids_raw, limit):
        if invoice_ids_raw:
            try:
                ids = [int(part.strip()) for part in invoice_ids_raw.split(",") if part.strip()]
            except ValueError as exc:
                raise CommandError(
                    f"Format de --invoice-ids invàlid ({invoice_ids_raw}). "
                    "Usa enters separats per comes."
                ) from exc
            if not ids:
                raise CommandError("--invoice-ids està buit.")

            qs = Invoice.objects.filter(pk__in=ids, type_final="F").exclude(status_id=1)
            if billing is not None:
                qs = qs.filter(billing=billing)

            found = list(qs.order_by("id").values_list("id", flat=True))
            missing = sorted(set(ids) - set(found))
            if missing:
                raise CommandError(
                    f"Factures no vàlides o no trobades (type_final='F', "
                    f"status_id≠1"
                    + (f", billing_id={billing.id}" if billing else "")
                    + f"): {missing}"
                )
            return found

        qs = (
            Invoice.objects.filter(billing=billing, type_final="F")
            .exclude(status_id=1)
            .order_by("id")
            .values_list("id", flat=True)
        )
        if limit is not None:
            qs = qs[:limit]
        return list(qs)

    def _handle_dry_run(self, results, output_dir, billing_id, invoice_ids):
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
                        "invoice_ids": invoice_ids,
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
                f"Dry-run OK: {len(results)} lot(s), {len(invoice_ids)} factura(es)"
            )
        )
