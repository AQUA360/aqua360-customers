"""
Reverteix una remesa SEPA enviada.

Efectes:
  1. Tots els pagaments de la remesa tornen a estat 'Pendent'
     (paid_at i payment_date es posen a NULL)
  2. Les factures associades tornen a estat 'Confirmada'
  3. Els registres PaymentMovement lligats a la remesa s'eliminen
  4. Els pagaments es desvinculen de la remesa (M2M clear)
  5. La remesa queda amb sent_at=NULL, sent_by=NULL i estat 'Pendent d'enviament'

Ús:
  python manage.py rollback_sepa_remittance <token>
  python manage.py rollback_sepa_remittance <token> --dry-run
  python manage.py rollback_sepa_remittance <token> --delete-remittance
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Reverteix una remesa SEPA enviada i deixa els pagaments preparats per tornar a remesar"

    def add_arguments(self, parser):
        parser.add_argument("token", type=str, help="Token de la remesa SEPA a revertir")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra el que es faria sense aplicar cap canvi",
        )
        parser.add_argument(
            "--delete-remittance",
            action="store_true",
            help="Elimina la remesa completament en lloc de restablir-la",
        )

    def handle(self, *args, **options):
        from billing.models import (
            InvoiceStatus, Payment, PaymentMovement,
            PaymentRemittance, PaymentRemittanceStatus, PaymentStatus,
        )
        from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
        from coredata.models import ConfigProject

        token = options["token"]
        dry_run = options["dry_run"]
        delete_remittance = options["delete_remittance"]

        # --- Obtenir la remesa ---
        try:
            remittance = PaymentRemittance.objects.select_related("status", "sent_by").get(token=token)
        except PaymentRemittance.DoesNotExist:
            raise CommandError(f"No s'ha trobat cap remesa amb token '{token}'")

        self.stdout.write(f"\nRemesa trobada:")
        self.stdout.write(f"  Token     : {remittance.token}")
        self.stdout.write(f"  Estat     : {remittance.status}")
        self.stdout.write(f"  Enviada el: {remittance.sent_at}")
        self.stdout.write(f"  Enviada per: {remittance.sent_by}")
        self.stdout.write(f"  Pagaments : {remittance.payments.count()}")

        if remittance.sent_at is None:
            raise CommandError("La remesa no ha estat enviada (sent_at és NULL). No cal revertir.")

        # --- Obtenir estats necessaris ---
        payment_status_pending_token = ConfigProject.objects.get(token="payment_status_pending_token").value
        payment_status_pending = PaymentStatus.objects.get(token=payment_status_pending_token)

        invoice_status_confirmed_token = ConfigProject.objects.get(token="invoice_status_confirmed_token").value
        invoice_status_confirmed = InvoiceStatus.objects.get(token=invoice_status_confirmed_token)

        remittance_status_pending = PaymentRemittanceStatus.objects.get(token="0")  # Pendent d'enviament

        # --- Recopilar dades ---
        payment_ids = list(remittance.payments.values_list("id", flat=True))
        invoice_ids = list(
            Payment.objects.filter(id__in=payment_ids, invoice__isnull=False)
            .values_list("invoice_id", flat=True)
            .distinct()
        )
        movement_ids = list(
            PaymentMovement.objects.filter(payment_remittance=remittance).values_list("id", flat=True)
        )

        self.stdout.write(f"\nAccions a realitzar:")
        self.stdout.write(f"  - Pagaments a revertir         : {len(payment_ids)}")
        self.stdout.write(f"  - Factures a tornar a Confirmada: {len(invoice_ids)}")
        self.stdout.write(f"  - Moviments de pagament a eliminar: {len(movement_ids)}")
        if delete_remittance:
            self.stdout.write(f"  - La remesa s'ELIMINARÀ")
        else:
            self.stdout.write(f"  - La remesa es restablirà (sent_at=NULL, estat=Pendent d'enviament)")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] Cap canvi aplicat."))
            return

        # --- Confirmació interactiva ---
        confirm = input("\nContinuar? [s/N] ").strip().lower()
        if confirm not in ("s", "si", "sí", "y", "yes"):
            self.stdout.write("Operació cancel·lada.")
            return

        # --- Aplicar canvis dins una transacció ---
        with transaction.atomic():
            disconnect_payment_signals()

            # 1. Revertir pagaments
            Payment.objects.filter(id__in=payment_ids).update(
                status=payment_status_pending,
                paid_at=None,
                payment_date=None,
            )
            self.stdout.write(f"  ✓ {len(payment_ids)} pagaments revertits a Pendent")

            # 2. Actualitzar factures a Confirmada
            from billing.models import Invoice
            Invoice.objects.filter(id__in=invoice_ids).update(
                status=invoice_status_confirmed,
            )
            self.stdout.write(f"  ✓ {len(invoice_ids)} factures tornades a Confirmada")

            # 3. Eliminar moviments de pagament lligats a la remesa
            deleted_count, _ = PaymentMovement.objects.filter(id__in=movement_ids).delete()
            self.stdout.write(f"  ✓ {deleted_count} moviments de pagament eliminats")

            # 4. Desvinc ular pagaments de la remesa
            remittance.payments.clear()
            self.stdout.write(f"  ✓ Pagaments desvinculats de la remesa")

            # 5. Restablir o eliminar la remesa
            if delete_remittance:
                remittance.delete()
                self.stdout.write(f"  ✓ Remesa eliminada")
            else:
                remittance.sent_at = None
                remittance.sent_by = None
                remittance.status = remittance_status_pending
                remittance.save(update_fields=["sent_at", "sent_by", "status"])
                self.stdout.write(f"  ✓ Remesa restablerta a Pendent d'enviament")

            reconnect_payment_signals()

        self.stdout.write(self.style.SUCCESS(
            f"\nRemesa '{token}' revertida correctament. "
            f"Els {len(payment_ids)} pagaments estan preparats per tornar a ser remesats."
        ))
