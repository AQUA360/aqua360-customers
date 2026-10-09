from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal
from typing import Dict, List, Optional

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from contract.models import Bail, BailStatus, Contract
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token

# "DES DE" / "FINS A" / "IMPORT" — taula de preus de fiances per data d'alta original.
# `until=None` vol dir "sense límit superior" (s'aplica a partir de `since`).
PRICE_TABLE = [
    {"since": None, "until": date(1988, 6, 27), "amount": Decimal("0.00")},
    {"since": date(1988, 6, 28), "until": date(1998, 1, 13), "amount": Decimal("6.01")},
    {"since": date(1998, 1, 14), "until": date(2008, 12, 31), "amount": Decimal("12.02")},
    {"since": date(2009, 1, 1), "until": date(2011, 1, 14), "amount": Decimal("20.00")},
    {"since": date(2011, 1, 15), "until": date(2016, 12, 31), "amount": Decimal("21.00")},
    {"since": date(2017, 1, 1), "until": None, "amount": Decimal("0.00")},
]

# Sufix de canvi de nom afegit pel sistema al contracte antic: "<base_token>/0001".
SUFFIX_RE = re.compile(r"/\d+$")


def _base_token(token: str) -> str:
    return SUFFIX_RE.sub("", token) if token else token


def _is_current_token(token: str, base_token: str) -> bool:
    return token == base_token


def _price_for_date(original_date: date) -> Decimal:
    for row in PRICE_TABLE:
        if row["since"] is not None and original_date < row["since"]:
            continue
        if row["until"] is not None and original_date > row["until"]:
            continue
        return row["amount"]
    # No hauria de passar (la taula cobreix tot l'eix temporal), però per seguretat:
    return Decimal("0.00")


def _contract_original_date(contract: Contract) -> date:
    if contract.registration_date:
        return contract.registration_date
    return contract.created_at.date() if contract.created_at else timezone.now().date()


class Command(BaseCommand):
    help = (
        "Crea una fiança (Bail) per a cada contracte físic existent (agrupant les "
        "cadenes de canvi de nom pel mateix token base), calculant l'import segons "
        "la data d'alta original del contracte més antic de la cadena i vinculant-la "
        "al contracte/titular actual."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No escriu res a BD; només mostra què es crearia.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limita el nombre de famílies de contractes a processar (per proves).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: Optional[int] = options["limit"]

        contracts = list(
            Contract.objects.exclude(token__isnull=True).exclude(token="").order_by("id")
        )
        if not contracts:
            self.stdout.write(self.style.WARNING("No hi ha contractes amb token."))
            return

        families: Dict[str, List[Contract]] = defaultdict(list)
        for contract in contracts:
            families[_base_token(contract.token)].append(contract)

        bail_status_unreturned_token = ConfigProject.objects.get(
            token="bail_status_unreturned_token"
        ).value
        unreturned_status = BailStatus.objects.get(token=bail_status_unreturned_token)

        created = 0
        skipped_existing = 0
        skipped_no_current = 0
        skipped_zero_amount = 0
        processed_families = 0

        family_items = list(families.items())
        if limit is not None:
            family_items = family_items[:limit]

        for base_token, family_contracts in family_items:
            processed_families += 1

            already_has_bail = any(
                Bail.objects.filter(contract=c).exists() for c in family_contracts
            )
            if already_has_bail:
                skipped_existing += 1
                continue

            current_contract = next(
                (c for c in family_contracts if _is_current_token(c.token, base_token)),
                None,
            )
            if current_contract is None:
                # Cap contracte de la família té el token "net" (tots porten sufix
                # /NNNN): la família es dona per tancada del tot, agafem el més recent
                # com a "actual" per no perdre la fiança.
                current_contract = max(
                    family_contracts, key=lambda c: (c.registration_date or c.created_at.date() if c.created_at else date.min)
                )
                skipped_no_current += 1

            original_contract = min(family_contracts, key=_contract_original_date)
            original_date = _contract_original_date(original_contract)
            amount = _price_for_date(original_date)

            if amount == 0:
                skipped_zero_amount += 1
                if dry_run:
                    self.stdout.write(
                        f"[DRY-RUN] Família {base_token}: import 0,00 (original={original_date}) "
                        "-> no es crea fiança."
                    )
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] Família {base_token}: {len(family_contracts)} contracte(s), "
                    f"original={original_date} (contract id={original_contract.id}), "
                    f"import={amount}, created_at fiança={original_date}, "
                    f"fiança vinculada a contract id={current_contract.id} "
                    f"(token={current_contract.token}, holder={current_contract.holder_id})"
                )
                continue

            original_created_at = timezone.make_aware(datetime.combine(original_date, time.min))

            with transaction.atomic():
                bail = Bail.objects.create(
                    token=generate_token(Bail),
                    contract=current_contract,
                    product=None,
                    price_rate=None,
                    amount=amount,
                    payment_date=None,
                    invoice=None,
                    return_date=None,
                    status=unreturned_status,
                    created_at=original_created_at,
                    updated_at=timezone.now(),
                    is_active=True,
                    is_billing=False,
                )
                # created_at és auto_now_add: cal forçar-lo explícitament després del create().
                Bail.objects.filter(pk=bail.pk).update(created_at=original_created_at)
                current_contract.bails.add(bail)

            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "OK. "
                f"Famílies processades={processed_families}, "
                f"fiances creades={created}, "
                f"ja tenien fiança={skipped_existing}, "
                f"import 0,00 (no creades)={skipped_zero_amount}, "
                f"sense contracte actual (token base sencer)={skipped_no_current}"
            )
        )
