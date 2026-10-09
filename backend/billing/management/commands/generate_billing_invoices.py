"""
Genera i confirma factures per a Billings de demo ja preparats (status Processat, lots de lectura associats).

Ús:
    python manage.py generate_billing_invoices --limit 1
    python manage.py generate_billing_invoices --limit 3 --sync
    python manage.py generate_billing_invoices --limit 1 --dry-run
    python manage.py generate_billing_invoices --billing-id 42 --force
    python manage.py generate_billing_invoices --limit 1 --no-confirm
    python manage.py generate_billing_invoices --limit 1 --no-pay
"""

from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Exists, OuterRef, Q

from billing.models import Billing, BillingStatus, Invoice, InvoiceStatus, Payment, Reading, ReadingBatch
from billing.tasks import process_billing_batch, process_invoice_documents
from billing.utils.payment_service import (
    disconnect_payment_signals,
    get_status_map,
    log_invoice_status,
    reconnect_payment_signals,
)
from coredata.models import ConfigProject
from billing.utils.reading_filters import PENDING_READING_FILTER


class Command(BaseCommand):
    help = (
        "Genera i confirma factures per a Billings amb status Processat (token 4 per defecte) "
        "que tenen el lot de lectura associat (ReadingBatch.token = Billing.token). "
        "Selecciona del més recent al més antic i aplica un límit."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=1,
            help="Nombre màxim de Billings a processar (per defecte: 1).",
        )
        parser.add_argument(
            '--status-token',
            type=str,
            default='4',
            help="Token del BillingStatus a filtrar (per defecte: 4 = Processat).",
        )
        parser.add_argument(
            '--billing-id',
            type=int,
            default=None,
            help="Processa un Billing concret per id (ignora --limit).",
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help="Executa process_billing_batch de forma síncrona (sense Celery).",
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help="Elimina factures existents del Billing abans de regenerar-les.",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Mostra quins Billings es processarien sense fer canvis.",
        )
        parser.add_argument(
            '--no-confirm',
            action='store_true',
            help="Només genera pre-factures (process_billing_batch), sense confirmar-les.",
        )
        parser.add_argument(
            '--no-pay',
            action='store_true',
            help="No marca les factures confirmades com a pagades (per defecte es marquen pagades).",
        )

    def handle(self, *args, **options):
        limit = options['limit']
        status_token = options['status_token']
        billing_id = options['billing_id']
        sync = options['sync']
        force = options['force']
        dry_run = options['dry_run']
        confirm = not options['no_confirm']
        mark_paid = not options['no_pay']

        if limit < 1 and billing_id is None:
            raise CommandError('--limit ha de ser >= 1.')

        status = BillingStatus.objects.filter(token=status_token).first()
        if not status:
            raise CommandError(f"No s'ha trobat BillingStatus amb token '{status_token}'.")

        billings = self._get_eligible_billings(status, billing_id, limit, force)

        if not billings:
            self.stdout.write(
                self.style.WARNING(
                    "No s'han trobat Billings elegibles "
                    f"(status={status_token}, lot de lectura associat"
                    + (", sense factures" if not force else "")
                    + ")."
                )
            )
            return

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Billings a processar: {len(billings)} "
                f"({'síncron' if sync else 'Celery'}, "
                f"{'amb confirmació' if confirm else 'sense confirmació'}"
                f"{', amb pagament' if confirm and mark_paid else ''})"
            )
        )
        for billing in billings:
            batch = ReadingBatch.objects.filter(token=billing.token).first()
            readings_count = batch.readings.filter(is_active=True).count() if batch else 0
            invoices_count = billing.invoices.count()
            self.stdout.write(
                f"  · id={billing.id} token={billing.token} "
                f"created_at={billing.created_at:%Y-%m-%d} "
                f"lectures={readings_count} factures={invoices_count}"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Mode dry-run: no s'ha fet cap canvi."))
            return

        processing_status = self._get_processing_status()
        results = []

        for billing in billings:
            assigned = self._assign_readings(billing)
            linked_readings = billing.readings.filter(is_active=True).count()
            if assigned == 0 and linked_readings == 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Billing {billing.id} ({billing.token}): cap lectura vinculada, s'omet."
                    )
                )
                continue
            if assigned == 0 and linked_readings > 0:
                self.stdout.write(
                    self.style.NOTICE(
                        f"  Billing {billing.id} ({billing.token}): "
                        f"{linked_readings} lectures ja vinculades (cap assignació nova per rutes)."
                    )
                )

            if force or billing.invoices.exists():
                self._clear_invoices(billing)

            billing.refresh_from_db()
            billing.status = processing_status
            billing.save(update_fields=['status'])

            batch_result = self._run_billing_batch(billing, sync)
            billing.refresh_from_db()
            invoices_created = batch_result.get('counters', {}).get('total', 0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Billing {billing.id} ({billing.token}): "
                    f"{invoices_created} pre-factures generades "
                    f"({assigned} lectures assignades)."
                )
            )

            confirm_result = None
            paid_count = 0
            if confirm and invoices_created > 0:
                confirm_result = self._confirm_invoices(billing, sync)
                billing.refresh_from_db()
                confirmed_count = confirm_result.get('counters', {}).get('total', 0)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Billing {billing.id} ({billing.token}): "
                        f"{confirmed_count} factures confirmades "
                        f"(status={billing.status.token if billing.status else None})."
                    )
                )
                if mark_paid:
                    paid_count = self._mark_invoices_as_paid(billing)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Billing {billing.id} ({billing.token}): "
                            f"{paid_count} factures marcades com a pagades."
                        )
                    )
            elif confirm and invoices_created == 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Billing {billing.id} ({billing.token}): "
                        "cap pre-factura generada, s'omet la confirmació."
                    )
                )

            results.append({
                'billing_id': billing.id,
                'batch_result': batch_result,
                'confirm_result': confirm_result,
                'paid_count': paid_count,
            })

        if not results:
            self.stdout.write(self.style.WARNING("Cap Billing processat."))

    def _get_eligible_billings(self, status, billing_id, limit, force):
        has_batch_with_readings = ReadingBatch.objects.filter(
            token=OuterRef('token'),
            readings__is_active=True,
        )

        qs = (
            Billing.objects.filter(
                status=status,
                biller__isnull=False,
                is_active=True,
            )
            .annotate(has_batch=Exists(has_batch_with_readings))
            .filter(has_batch=True)
            .order_by('-created_at')
        )

        if not force:
            qs = qs.annotate(invoice_count=Count('invoices')).filter(invoice_count=0)

        if billing_id is not None:
            billing = qs.filter(id=billing_id).first()
            if not billing:
                raise CommandError(
                    f"Billing id={billing_id} no trobat o no compleix els criteris."
                )
            return [billing]

        return list(qs[:limit])

    def _get_processing_status(self):
        token = ConfigProject.objects.get(token='billing_batch_processing').value
        return BillingStatus.objects.get(token=token)

    def _run_billing_batch(self, billing, sync):
        if sync:
            return process_billing_batch(billing.id)

        from celery.result import AsyncResult

        task = process_billing_batch.delay(billing.id)
        billing.task_id = task.id
        billing.save(update_fields=['task_id'])
        self.stdout.write(f"    Esperant process_billing_batch (task_id={task.id})...")
        return AsyncResult(task.id).get(timeout=3600)

    def _confirm_invoices(self, billing, sync):
        invoice_ids = list(billing.invoices.values_list('id', flat=True))
        if not invoice_ids:
            return {'counters': {'total': 0}}

        issue_date, end_date, send_at = self._get_billing_dates(billing)
        self.stdout.write(
            f"    Dates confirmació: issue={issue_date}, venciment={end_date}, enviament={send_at}"
        )
        context = {'base_url': getattr(settings, 'DOMAIN_MEDIA', None) or 'http://127.0.0.1:8000'}

        processing_docs_status = BillingStatus.objects.get(
            token=ConfigProject.objects.get(token='billing_batch_processing_documents').value
        )
        billing.status = processing_docs_status
        billing.save(update_fields=['status'])

        if sync:
            return process_invoice_documents(
                billing.id, invoice_ids, context, issue_date, end_date, send_at
            )

        from celery.result import AsyncResult

        task = process_invoice_documents.delay(
            billing.id, invoice_ids, context, issue_date, end_date, send_at
        )
        billing.task_id = task.id
        billing.save(update_fields=['task_id'])
        self.stdout.write(f"    Esperant process_invoice_documents (task_id={task.id})...")
        return AsyncResult(task.id).get(timeout=3600)

    def _get_billing_dates(self, billing):
        """Dates basades en el període del billing, no en avui."""
        reference_dt = billing.send_at or billing.created_at
        if not reference_dt:
            return None, None, None

        base_date = reference_dt.date() if hasattr(reference_dt, 'date') else reference_dt
        issue_date = base_date.strftime('%Y-%m-%d')
        end_date = (base_date + relativedelta(months=1)).strftime('%Y-%m-%d')
        send_at = (base_date + timedelta(weeks=1)).strftime('%Y-%m-%d')
        return issue_date, end_date, send_at

    def _mark_invoices_as_paid(self, billing):
        payment_status_map = get_status_map()
        paid_payment_status = payment_status_map['payment_status_paid_token']
        paid_invoice_status = InvoiceStatus.objects.get(
            token=ConfigProject.objects.get(token='invoice_status_paid_token').value
        )
        user = get_user_model().objects.filter(is_superuser=True).first()

        disconnect_payment_signals()
        marked = 0
        try:
            for invoice in billing.invoices.prefetch_related('payments'):
                for payment in invoice.payments.all():
                    if payment.status_id == paid_payment_status.id:
                        continue
                    payment.status = paid_payment_status
                    payment._skip_signal = True
                    payment.save(update_fields=['status'])

                if invoice.status_id != paid_invoice_status.id:
                    invoice.status = paid_invoice_status
                    invoice._skip_signal = True
                    invoice.save(update_fields=['status'])
                    log_invoice_status(invoice, paid_invoice_status, user)
                    marked += 1
        finally:
            reconnect_payment_signals()

        return marked

    def _assign_readings(self, billing):
        """Assigna lectures al billing (mateixa lògica que import_billing + UI assign-readings)."""
        batch_tokens = self._get_reading_batch_tokens(billing)
        if not batch_tokens:
            return 0

        billing_supply_point_ids = set(
            billing.routes.values_list(
                'positions__properties__supply_points__id',
                flat=True,
            ).distinct()
        )
        billing_supply_point_ids.discard(None)

        assigned = 0
        for batch_token in batch_tokens:
            reading_batch = ReadingBatch.objects.filter(token=batch_token).first()
            if not reading_batch:
                continue

            readings_qs = Reading.objects.filter(
                batch=reading_batch,
                is_active=True,
            ).filter(
                PENDING_READING_FILTER
            ).distinct()

            # UI: filtra per supply points de les rutes del billing.
            # Demo/import: si no hi ha coincidència de rutes, assigna tot el lot (com import_billing).
            if billing_supply_point_ids:
                route_filtered = readings_qs.filter(
                    supply_point_id__in=billing_supply_point_ids
                )
                if route_filtered.exists():
                    readings_qs = route_filtered
                # else: fallback a tot el lot, igual que BillingService.update_from_csv

            assigned += readings_qs.update(billing=billing)

        return assigned

    def _get_reading_batch_tokens(self, billing):
        if billing.token:
            return [billing.token]
        return []

    def _clear_invoices(self, billing):
        excluded_billings = Billing.objects.filter(excluded_from_id=billing.id)
        for ex_billing in excluded_billings:
            Reading.objects.filter(billing=ex_billing).update(billing_id=billing.id)
            Invoice.objects.filter(billing=ex_billing).delete()
            ex_billing.delete()

        Invoice.objects.filter(billing=billing).delete()
