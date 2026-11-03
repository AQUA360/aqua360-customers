import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from billing.models import Billing, CommitmentDeposit
from coredata.models import ConfigProject
from integrations.outbound.odoo.exceptions import OdooApiError, OdooMappingError
from integrations.outbound.odoo.services import push_commitment_deposit_batch


class Command(BaseCommand):
    help = (
        "Envia un lot de compromisos (CommitmentDeposit) a Odoo (bulk ≤1000) "
        "creant SendBatch, o genera el JSON del lot amb --dry-run. "
        "Acció create → /batch/commitment/create; cancel → /batch/commitment/cancel. "
        "Amb --no-send crea SendBatch sense fer POST a Odoo. "
        "Accepta --commitment-ids i/o --billing-id / --contract-id."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--action",
            dest="action",
            choices=["create", "cancel"],
            default="create",
            help="create (per defecte) o cancel del compromís a Odoo.",
        )
        parser.add_argument(
            "--billing-id",
            dest="billing_id",
            type=int,
            default=None,
            help=(
                "ID de billing.Billing. Filtra compromisos via factures vinculades "
                "(invoices__billing)."
            ),
        )
        parser.add_argument(
            "--contract-id",
            dest="contract_id",
            type=int,
            default=None,
            help="ID de contract.Contract.",
        )
        parser.add_argument(
            "--commitment-ids",
            dest="commitment_ids",
            default="",
            help="Llista d'IDs de CommitmentDeposit separats per comes (p.ex. 10,11,12).",
        )
        parser.add_argument(
            "--date",
            dest="date",
            default=None,
            help=(
                "Data YYYY-MM-DD forçada al payload (create/cancel). "
                "Si no s'informa: start_date/created_at (create) o updated_at (cancel)."
            ),
        )
        parser.add_argument(
            "--include-cancelled",
            action="store_true",
            help=(
                "En create, també inclou compromisos anul·lats "
                "(per defecte s'exclouen)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Només genera el JSON del lot sense cridar Odoo ni crear SendBatch.",
        )
        parser.add_argument(
            "--no-send",
            action="store_true",
            help="Crea SendBatch i relaciona compromisos, però no fa POST a l'endpoint d'Odoo.",
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
            help="Màxim de compromisos.",
        )

    def handle(self, *args, **options):
        action = options["action"]
        billing_id = options["billing_id"]
        contract_id = options["contract_id"]
        commitment_ids_raw = (options["commitment_ids"] or "").strip()
        date_raw = options["date"]
        include_cancelled = options["include_cancelled"]
        output_dir = (options["output_dir"] or "").strip()
        dry_run = options["dry_run"] or bool(output_dir)
        no_send = options["no_send"]
        limit = options["limit"]

        has_filter = any([billing_id, contract_id, commitment_ids_raw])
        if not has_filter:
            raise CommandError(
                "Cal indicar --commitment-ids i/o --billing-id / --contract-id."
            )
        if dry_run and no_send:
            raise CommandError("--dry-run i --no-send són incompatibles.")

        billing = None
        if billing_id is not None:
            try:
                billing = Billing.objects.get(pk=billing_id)
            except Billing.DoesNotExist as exc:
                raise CommandError(f"Billing {billing_id} no trobat.") from exc

        date_override = None
        if date_raw:
            date_override = self._parse_date(date_raw, "--date")

        commitment_ids = self._resolve_commitment_ids(
            action=action,
            billing=billing,
            contract_id=contract_id,
            commitment_ids_raw=commitment_ids_raw,
            include_cancelled=include_cancelled,
            limit=limit,
        )
        if not commitment_ids:
            raise CommandError(
                "No s'ha trobat cap compromís amb els criteris indicats."
            )

        mode = "dry-run" if dry_run else ("no-send" if no_send else "send")
        self.stdout.write(
            f"Lot ({action}): {len(commitment_ids)} compromís(os)"
            + (f" | billing_id={billing.id}" if billing else "")
            + (f" | contract_id={contract_id}" if contract_id else "")
            + f" | {mode}"
        )

        try:
            results = push_commitment_deposit_batch(
                commitment_ids,
                action=action,
                billing=billing,
                dry_run=dry_run,
                send=not no_send,
                date_override=date_override,
            )
        except OdooMappingError as exc:
            raise CommandError(f"Error de mapatge: {exc}") from exc
        except OdooApiError as exc:
            raise CommandError(f"Error API Odoo: {exc}") from exc

        if dry_run:
            self._handle_dry_run(
                results, output_dir, billing_id, commitment_ids, action
            )
            return

        for batch in results:
            self.stdout.write(
                self.style.SUCCESS(
                    f"SendBatch {batch.token} creat "
                    f"(id={batch.id}, http={batch.instant_status_code}, "
                    f"status={batch.status.token if batch.status else None}, "
                    f"commitment_deposits={batch.commitment_deposits.count()})"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Lots {'creats (sense enviament)' if no_send else 'enviats'}: "
                f"{len(results)}"
            )
        )

    def _parse_date(self, raw, flag_name):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(
                f"Format de {flag_name} invàlid ({raw}). Usa YYYY-MM-DD."
            ) from exc

    def _cancelled_status_token(self):
        try:
            return ConfigProject.objects.get(
                token="commitment_deposit_status_cancelled_token"
            ).value
        except ConfigProject.DoesNotExist:
            return "-1"

    def _base_queryset(self, *, action, include_cancelled):
        qs = CommitmentDeposit.objects.all()
        cancelled_token = self._cancelled_status_token()
        if action == "cancel":
            # Només anul·lats a Aqua (també amb --commitment-ids).
            qs = qs.filter(status__token=cancelled_token)
        elif not include_cancelled:
            qs = qs.exclude(status__token=cancelled_token)
        return qs

    def _apply_filters(self, qs, *, billing, contract_id):
        if billing is not None:
            qs = qs.filter(invoices__billing=billing)
        if contract_id is not None:
            qs = qs.filter(contract_id=contract_id)
        return qs

    def _resolve_commitment_ids(
        self,
        *,
        action,
        billing,
        contract_id,
        commitment_ids_raw,
        include_cancelled,
        limit,
    ):
        if commitment_ids_raw:
            try:
                ids = [
                    int(part.strip())
                    for part in commitment_ids_raw.split(",")
                    if part.strip()
                ]
            except ValueError as exc:
                raise CommandError(
                    f"Format de --commitment-ids invàlid ({commitment_ids_raw}). "
                    "Usa enters separats per comes."
                ) from exc
            if not ids:
                raise CommandError("--commitment-ids està buit.")

            qs = self._apply_filters(
                self._base_queryset(
                    action=action, include_cancelled=include_cancelled
                ).filter(pk__in=ids),
                billing=billing,
                contract_id=contract_id,
            )

            found = list(qs.order_by("id").values_list("id", flat=True).distinct())
            missing = sorted(set(ids) - set(found))
            if missing:
                hint = (
                    "anul·lats"
                    if action == "cancel"
                    else "no anul·lats (o usa --include-cancelled)"
                )
                raise CommandError(
                    f"Compromisos no vàlids o no trobats ({hint}"
                    + (f", billing_id={billing.id}" if billing else "")
                    + (f", contract_id={contract_id}" if contract_id else "")
                    + f"): {missing}"
                )
            return found

        qs = self._apply_filters(
            self._base_queryset(action=action, include_cancelled=include_cancelled),
            billing=billing,
            contract_id=contract_id,
        )
        qs = qs.order_by("id").values_list("id", flat=True).distinct()
        if limit is not None:
            qs = qs[:limit]
        return list(qs)

    def _handle_dry_run(self, results, output_dir, billing_id, commitment_ids, action):
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
                        "action": action,
                        "dry_run": True,
                        "commitment_ids": commitment_ids,
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
                f"Dry-run OK: {len(results)} lot(s), "
                f"{len(commitment_ids)} compromís(os) ({action})"
            )
        )
