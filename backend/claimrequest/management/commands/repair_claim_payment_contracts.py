from django.core.management.base import BaseCommand
from django.db import transaction

from claimrequest.models import ClaimRequest, ClaimRequestPayment
from claimrequest.tasks import (
    claim_request_groups_payments_without_rates,
    create_joined_payments_for_claim_request,
)
from claimrequest.utils.claim_request_service import resolve_invoice_contract
from coredata.models import ConfigProject


class Command(BaseCommand):
    help = (
        "Omple el contracte dels pagaments d'una gestió d'impagats que el tenen buit "
        "(factures emeses durant una sol·licitud d'alta o una baixa) i completa el "
        "pagament agrupat que faltava. Sense contracte, la carta del pas surt sense "
        "codi de barres i la comunicació no hi arriba."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa el script sense fer canvis reals a la base de dades',
        )
        parser.add_argument(
            '--claim-token',
            type=str,
            help="Processa només una gestió concreta pel seu token",
        )
        parser.add_argument(
            '--all-statuses',
            action='store_true',
            help='Processa totes les gestions, no només les obertes (pendents i acceptades)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        claim_token = options.get('claim_token')
        all_statuses = options['all_statuses']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 MODE DRY-RUN: no es faran canvis reals a la base de dades')
            )

        claims = ClaimRequest.objects.all()
        if claim_token:
            claims = claims.filter(token=claim_token)
        elif not all_statuses:
            open_tokens = list(
                ConfigProject.objects.filter(
                    token__in=[
                        'claim_request_status_accepted_token',
                        'claim_request_status_pending_token',
                    ]
                ).values_list('value', flat=True)
            )
            if not open_tokens:
                self.stdout.write(
                    self.style.ERROR(
                        "❌ No s'han trobat els tokens d'estat de gestió oberta. "
                        "Fes servir --all-statuses si vols processar-les totes."
                    )
                )
                return
            claims = claims.filter(status__token__in=open_tokens)

        claims = claims.select_related('current_step', 'current_step__step_template').order_by('id')
        self.stdout.write(f"🔍 Gestions a revisar: {claims.count()}")

        filled = 0
        unresolved = 0
        joined_payments_touched = 0
        claims_touched = 0

        with transaction.atomic():
            for claim in claims:
                orphan_payments = ClaimRequestPayment.objects.filter(
                    claim_request=claim,
                    contract__isnull=True,
                ).select_related(
                    'payment',
                    'payment__invoice',
                    'payment__invoice__contract',
                    'payment__invoice__contract_request',
                    'payment__invoice__contract_termination',
                )
                if not orphan_payments.exists():
                    continue

                self.stdout.write(f"\n📋 Gestió {claim.token}: {orphan_payments.count()} pagaments sense contracte")
                claim_filled = 0
                for claim_payment in orphan_payments:
                    invoice = claim_payment.payment.invoice if claim_payment.payment else None
                    contract = resolve_invoice_contract(invoice)
                    if not contract:
                        unresolved += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"   ⚠️  Factura {invoice.serie_final if invoice else '—'}: "
                                "la sol·licitud no té contracte, no es pot reclamar"
                            )
                        )
                        continue
                    if not dry_run:
                        claim_payment.contract = contract
                        claim_payment.save(update_fields=['contract'])
                    claim_filled += 1
                    filled += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ Factura {invoice.serie_final if invoice else '—'} → contracte {contract.token}"
                        )
                    )

                if not claim_filled:
                    continue

                claims_touched += 1
                # Mateixa condició que a l'alta de la gestió: amb tarifes al pas, els
                # agrupats els crea `generate_claim_expenses` factura a factura i no
                # s'han de tornar a crear aquí.
                if not claim_request_groups_payments_without_rates(claim):
                    self.stdout.write("   ⏭️  El pas no agrupa pagaments sense tarifes: no es toca l'agrupat")
                    continue
                if dry_run:
                    self.stdout.write("   🔍 [DRY-RUN] Crearia o completaria el pagament agrupat")
                    joined_payments_touched += 1
                    continue
                created = create_joined_payments_for_claim_request(claim)
                joined_payments_touched += len(created)
                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ Pagaments agrupats creats o completats: {len(created)}")
                )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write("\n📊 RESUM FINAL:")
        self.stdout.write(f"   - Gestions modificades: {claims_touched}")
        self.stdout.write(f"   - Pagaments amb contracte omplert: {filled}")
        self.stdout.write(f"   - Pagaments sense contracte possible: {unresolved}")
        self.stdout.write(f"   - Pagaments agrupats creats o completats: {joined_payments_touched}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🔍 Això ha estat un DRY-RUN. No s'ha fet cap canvi real.")
            )
