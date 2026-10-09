import logging

import schwifty
from django.core.management.base import BaseCommand

from coredata.models import Bank

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Corregeix el camp `bic` de Bank creuant el `token` (codi de banc ES) "
        "amb el registre BIC oficial de la llibreria schwifty. Per defecte només "
        "mostra les diferències, cal --apply per escriure els canvis a BD."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica els canvis a la base de dades. Sense aquest flag només s'informa (dry-run).",
        )
        parser.add_argument(
            "--fill-empty-only",
            action="store_true",
            help="Només omple bancs amb `bic` buit/null, sense tocar els que ja tenen un valor "
                 "(útil per no sobreescriure dades ja validades manualment).",
        )

    def _build_es_registry(self):
        reg = schwifty.registry.get('bank_code')
        registry = {}
        for key, value in reg.items():
            if key[0] != 'ES':
                continue
            entry = value[0] if isinstance(value, list) else value
            registry[key[1]] = entry
        return registry

    def handle(self, *args, **options):
        apply_changes = options.get("apply", False)
        fill_empty_only = options.get("fill_empty_only", False)

        registry = self._build_es_registry()
        self.stdout.write(f"Registre BIC ES carregat: {len(registry)} entrades.")

        banks = Bank.objects.all()
        total = banks.count()
        self.stdout.write(f"Processant {total} bancs...")

        updated = 0
        not_found = 0
        skipped_has_value = 0
        unchanged = 0

        for bank in banks.iterator(chunk_size=500):
            if not bank.token:
                not_found += 1
                continue

            token = bank.token.strip().zfill(4)
            ref = registry.get(token)
            if not ref or not ref.get('bic'):
                not_found += 1
                continue

            ref_bic = ref['bic']
            current_bic = (bank.bic or '').strip()

            if current_bic == ref_bic:
                unchanged += 1
                continue

            if fill_empty_only and current_bic:
                skipped_has_value += 1
                continue

            self.stdout.write(
                f"token={bank.token!r} name={bank.name!r} | "
                f"bic actual={current_bic!r} -> bic correcte={ref_bic!r} "
                f"(ref_name={ref.get('name')!r})"
            )

            if apply_changes:
                bank.bic = ref_bic
                bank.save(update_fields=['bic'])

            updated += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(self.style.SUCCESS("RESUM FIX BANK BIC"))
        self.stdout.write(self.style.SUCCESS("=" * 50))
        self.stdout.write(f"Total bancs: {total}")
        self.stdout.write(f"{'Actualitzats' if apply_changes else 'A actualitzar (dry-run)'}: {updated}")
        self.stdout.write(f"Sense canvis (ja correctes): {unchanged}")
        self.stdout.write(f"Sense correspondència al registre ES (token no trobat): {not_found}")
        if fill_empty_only:
            self.stdout.write(f"Ignorats per ja tenir valor (--fill-empty-only): {skipped_has_value}")
        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Mode dry-run: no s'ha escrit res a la BD. Executa amb --apply per aplicar els canvis."
            ))
