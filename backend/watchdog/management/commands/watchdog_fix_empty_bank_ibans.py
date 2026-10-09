from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import GeneralPayment, Invoice, PaymentCommitment, PaymentRemittance
from contract.models import Contract, ContractDataChange
from coredata.models import PersonBank
from coredata.utils.iban_validator_utils import validate_iban
from service.models import CompanyBank


def iban_is_invalid(iban):
    return not iban or not validate_iban(iban)


class Command(BaseCommand):
    help = (
        "Elimina PersonBank i CompanyBank amb IBAN buit o invàlid (mateix criteri que el watchdog sniff). "
        "Per defecte també esborra comptes referenciats: les FK amb on_delete=SET_NULL queden a NULL."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra què s'esborraria sense desar canvis",
        )
        parser.add_argument(
            "--skip-in-use",
            action="store_true",
            help="No esborra comptes encara referenciats (comportament conservador)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_in_use = options["skip_in_use"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("[DRY-RUN] No es desarà res a la base de dades")
            )

        person_in_use = self._person_bank_ids_in_use() if skip_in_use else set()
        company_in_use = self._company_bank_ids_in_use() if skip_in_use else set()

        person_to_delete = []
        person_skipped_in_use = []
        for pb in PersonBank.objects.all().only("id", "iban", "person_id"):
            if not iban_is_invalid(pb.iban):
                continue
            if skip_in_use and pb.id in person_in_use:
                person_skipped_in_use.append(pb)
                continue
            person_to_delete.append(pb)

        company_to_delete = []
        company_skipped_in_use = []
        for cb in CompanyBank.objects.all().only("id", "iban", "company_id"):
            if not iban_is_invalid(cb.iban):
                continue
            if skip_in_use and cb.id in company_in_use:
                company_skipped_in_use.append(cb)
                continue
            company_to_delete.append(cb)

        for pb in person_to_delete:
            prefix = "[dry-run] " if dry_run else ""
            refs = self._person_bank_reference_summary(pb.id)
            refs_text = (
                f" — referències que quedaran NULL: {refs}"
                if refs
                else ""
            )
            self.stdout.write(
                f"{prefix}Esborrar PersonBank id={pb.id} (Person id={pb.person_id}), "
                f"IBAN={pb.iban!r}{refs_text}"
            )

        for cb in company_to_delete:
            prefix = "[dry-run] " if dry_run else ""
            refs = self._company_bank_reference_summary(cb.id)
            refs_text = (
                f" — referències que quedaran NULL: {refs}"
                if refs
                else ""
            )
            self.stdout.write(
                f"{prefix}Esborrar CompanyBank id={cb.id} (Company id={cb.company_id}), "
                f"IBAN={cb.iban!r}{refs_text}"
            )

        for pb in person_skipped_in_use:
            self.stdout.write(
                self.style.WARNING(
                    f"PersonBank id={pb.id} (Person id={pb.person_id}): IBAN invàlid, "
                    f"referenciat; s'omet (--skip-in-use)"
                )
            )

        for cb in company_skipped_in_use:
            self.stdout.write(
                self.style.WARNING(
                    f"CompanyBank id={cb.id} (Company id={cb.company_id}): IBAN invàlid, "
                    f"referenciat; s'omet (--skip-in-use)"
                )
            )

        if not dry_run and (person_to_delete or company_to_delete):
            with transaction.atomic():
                if person_to_delete:
                    PersonBank.objects.filter(
                        id__in=[pb.id for pb in person_to_delete]
                    ).delete()
                if company_to_delete:
                    CompanyBank.objects.filter(
                        id__in=[cb.id for cb in company_to_delete]
                    ).delete()

        prefix = "S'esborrarien" if dry_run else "Esborrats"
        summary = (
            f"{prefix} {len(person_to_delete)} PersonBank i "
            f"{len(company_to_delete)} CompanyBank."
        )
        if skip_in_use:
            summary += (
                f" Omesos (--skip-in-use): {len(person_skipped_in_use)} PersonBank, "
                f"{len(company_skipped_in_use)} CompanyBank."
            )
        self.stdout.write(self.style.SUCCESS(summary))

    @staticmethod
    def _person_bank_reference_summary(person_bank_id):
        parts = []
        n = Contract.objects.filter(payment__IBAN_id=person_bank_id).count()
        if n:
            parts.append(f"ContractPayment={n}")
        n = GeneralPayment.objects.filter(IBAN_id=person_bank_id).count()
        if n:
            parts.append(f"GeneralPayment={n}")
        n = Invoice.objects.filter(payment_bank_id=person_bank_id).count()
        if n:
            parts.append(f"Invoice={n}")
        n = PaymentCommitment.objects.filter(payment_bank_id=person_bank_id).count()
        if n:
            parts.append(f"PaymentCommitment={n}")
        n = ContractDataChange.objects.filter(
            new_payment_id=person_bank_id
        ).count()
        if n:
            parts.append(f"ContractDataChange(new)={n}")
        n = ContractDataChange.objects.filter(
            previous_payment_id=person_bank_id
        ).count()
        if n:
            parts.append(f"ContractDataChange(prev)={n}")
        return ", ".join(parts)

    @staticmethod
    def _company_bank_reference_summary(company_bank_id):
        parts = []
        n = GeneralPayment.objects.filter(company_iban_id=company_bank_id).count()
        if n:
            parts.append(f"GeneralPayment={n}")
        n = Invoice.objects.filter(payment_company_bank_id=company_bank_id).count()
        if n:
            parts.append(f"Invoice={n}")
        n = PaymentRemittance.objects.filter(company_bank_id=company_bank_id).count()
        if n:
            parts.append(f"PaymentRemittance={n}")
        return ", ".join(parts)

    @staticmethod
    def _person_bank_ids_in_use():
        ids = set()
        ids.update(
            Contract.objects.filter(payment__IBAN__isnull=False).values_list(
                "payment__IBAN_id", flat=True
            )
        )
        ids.update(
            GeneralPayment.objects.filter(IBAN__isnull=False).values_list(
                "IBAN_id", flat=True
            )
        )
        ids.update(
            ContractDataChange.objects.filter(new_payment__isnull=False).values_list(
                "new_payment_id", flat=True
            )
        )
        ids.update(
            ContractDataChange.objects.filter(
                previous_payment__isnull=False
            ).values_list("previous_payment_id", flat=True)
        )
        ids.update(
            Invoice.objects.filter(payment_bank__isnull=False).values_list(
                "payment_bank_id", flat=True
            )
        )
        ids.update(
            PaymentCommitment.objects.filter(payment_bank__isnull=False).values_list(
                "payment_bank_id", flat=True
            )
        )
        ids.discard(None)
        return ids

    @staticmethod
    def _company_bank_ids_in_use():
        ids = set(
            GeneralPayment.objects.filter(company_iban__isnull=False).values_list(
                "company_iban_id", flat=True
            )
        )
        ids.update(
            Invoice.objects.filter(payment_company_bank__isnull=False).values_list(
                "payment_company_bank_id", flat=True
            )
        )
        ids.update(
            PaymentRemittance.objects.filter(company_bank__isnull=False).values_list(
                "company_bank_id", flat=True
            )
        )
        ids.discard(None)
        return ids
