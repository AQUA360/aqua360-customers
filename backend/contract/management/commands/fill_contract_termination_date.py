from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from django.core.management.base import BaseCommand

if TYPE_CHECKING:
    from django.apps.registry import Apps

logger = logging.getLogger(__name__)

Messenger = Callable[[str, str], None]


def fill_contract_termination_date_logic(
    *,
    apps: Apps | None = None,
    dry_run: bool = False,
    messenger: Messenger | None = None,
) -> None:
    """Omple ``termination_date`` per contractes en baixa.

    Si ``apps`` és el ``StateApps`` d'una migració, s'usen models històrics
    (sense columnes afegides més tard, p.ex. ``company_id`` abans del 0220).
    """

    def msg(text: str, level: str = "info") -> None:
        if messenger:
            messenger(text, level)
        else:
            print(text)

    if apps is not None:
        ConfigProject = apps.get_model("coredata", "ConfigProject")
        ContractStatus = apps.get_model("contract", "ContractStatus")
        Contract = apps.get_model("contract", "Contract")
        ContractLog = apps.get_model("contract", "ContractLog")
        ContractTerminationRequest = apps.get_model(
            "contract", "ContractTerminationRequest"
        )
    else:
        from contract.models import (
            Contract,
            ContractLog,
            ContractStatus,
            ContractTerminationRequest,
        )
        from coredata.models import ConfigProject

    try:
        terminated_token = ConfigProject.objects.get(
            token="contract_terminated_status"
        ).value
        baixa_status = ContractStatus.objects.get(token=terminated_token)
        baixa_name = str(baixa_status)
    except (ConfigProject.DoesNotExist, ContractStatus.DoesNotExist):
        msg("Configuració de 'Baixa' no trobada", "error")
        return

    contracts = Contract.objects.filter(status=baixa_status)
    total = contracts.count()
    msg(f"Processant {total} contractes en estat de baixa...")

    updated = 0
    skipped = 0
    errors = 0

    for contract in contracts:
        try:
            termination_date = None

            status_log = (
                ContractLog.objects.filter(
                    contract=contract,
                    field_name="status",
                    new_value=baixa_name,
                )
                .order_by("created_at")
                .first()
            )

            if status_log:
                termination_date = status_log.created_at.date()

            if not termination_date:
                req = (
                    ContractTerminationRequest.objects.filter(contract=contract)
                    .order_by("-approved_at", "-requested_at")
                    .first()
                )

                if req:
                    if req.approved_at:
                        termination_date = req.approved_at.date()
                    elif req.requested_at:
                        termination_date = req.requested_at.date()

            if termination_date:
                if contract.termination_date != termination_date:
                    if not dry_run:
                        contract.termination_date = termination_date
                        contract.save(update_fields=["termination_date"])
                    updated += 1
                else:
                    skipped += 1
            else:
                msg(
                    f"No s'ha trobat data de baixa pel contracte {contract.token}",
                    "warning",
                )
                skipped += 1

        except Exception as e:
            errors += 1
            logger.error(
                f"Error processant contracte {contract.id}: {str(e)}",
                exc_info=True,
            )
            msg(f"Error processant contracte {contract.id}: {str(e)}", "error")

    msg("")
    msg("=" * 50, "success")
    msg("RESUM", "success")
    msg("=" * 50, "success")
    msg(f"Total contractes processats: {total}")
    msg(f"Contractes actualitzats: {updated}", "success")
    msg(f"Saltats (sense canvi o sense data trobada): {skipped}")
    msg(f"Errors: {errors}")

    if dry_run:
        msg("\n⚠️  MODO DRY-RUN: No s'han fet canvis a la base de dades", "warning")


class Command(BaseCommand):
    help = "Omple el camp termination_date dels contractes a partir de l'historial de canvis o sol·licituds"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa el script sense fer canvis a la base de dades",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        def messenger(text: str, level: str = "info") -> None:
            if level == "error":
                self.stdout.write(self.style.ERROR(text))
            elif level == "warning":
                self.stdout.write(self.style.WARNING(text))
            elif level == "success":
                self.stdout.write(self.style.SUCCESS(text))
            else:
                self.stdout.write(text)

        fill_contract_termination_date_logic(
            apps=None, dry_run=dry_run, messenger=messenger
        )
