"""
Script autònom per recalcular factures d'un Billing.

Conserva la mateixa factura (mateix id, serie_final i data d'emissió).
Recalcula línies, consums, dies i imports com una factura normal.
Actualitza també les dades estàtiques de client, pagador i adreça.
Actualitza el pagament si canvia el total.

Ús:
    python manage.py recalculate_billing_invoices --billing-id 42 --dry-run --list-invoices
    python manage.py recalculate_billing_invoices --billing-id 42
    python manage.py recalculate_billing_invoices --billing-id 42 --invoice-ids 10,11,12
    python manage.py recalculate_billing_invoices --billing-id 42 --regenerate-pdf
"""

import calendar
import datetime

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import Billing, Invoice, Payment, PaymentStatus, Reading
from billing.utils.confirm_invoice_service import (
    _get_invoice_contract,
    _get_remittance_date,
    _parse_date,
    get_payment_status_token_for_invoice_status,
)
from billing.utils.invoice_service import check_piggy_bank, generate_consumption_invoice_multiple
from billing.utils.payment_service import disconnect_payment_signals, reconnect_payment_signals
from billing.utils.recalculate_invoice_service import _get_invoice_warning, _get_period_months
from contract.models import PaymentType
from coredata.models import ConfigProject


def _snapshot_invoice(invoice):
  payment = invoice.payments.filter(is_active=True).order_by("id").first()
  payment_data = None
  if payment:
    payment_data = {
      "token": payment.token,
      "status_id": payment.status_id,
      "paid_at": payment.paid_at,
      "due_date": payment.due_date,
      "payment_date": payment.payment_date,
      "sent_date": payment.sent_date,
      "is_active": payment.is_active,
    }
  return {
    "payment": payment_data,
    "original_id": invoice.id,
    "original_total": invoice.total_final,
  }


RECALCULATED_FIELDS = [
  "consumption",
  "consumption_days",
  "real_consumption",
  "responsible_consumption",
  "subtotal_final",
  "total_final",
  "left_to_pay",
  "exploitation_id",
  "company_id",
  "customer_final",
  "customer_token_final",
  "payer_final",
  "payer_token_final",
  "customer_is_juridic",
  "customer_tlf_final",
  "customer_email_final",
  "address_final",
  "postal_code_final",
  "city_final",
  "province_final",
  "location_final",
]


def _apply_recalculation_to_invoice(original, temp):
  reading_ids = list(temp.readings.values_list("id", flat=True))

  original.line_items.all().delete()

  line_items = list(temp.line_items.all().order_by("custom_order", "id"))
  for index, line_item in enumerate(line_items, start=1):
    line_item.invoice = original
    line_item.token = f"{original.number}-{index}"
    line_item.save(update_fields=["invoice", "token"])

  original.readings.set(reading_ids)

  for field in RECALCULATED_FIELDS:
    setattr(original, field, getattr(temp, field))
  original.warning = temp.warning
  original.save(update_fields=RECALCULATED_FIELDS + ["warning_id"])

  temp.readings.clear()
  temp.delete()


def _resolve_readings(original_readings):
  readings = []
  for reading in original_readings:
    if reading.is_control:
      modified = reading.modified_readings.filter(is_control=False).first()
      readings.append(modified if modified else reading)
    else:
      readings.append(reading)
  return readings


def _prepare_readings_billing(billing, readings):
  if not billing:
    return
  reading_ids = [reading.id for reading in readings]
  Reading.objects.filter(id__in=reading_ids).update(billing=billing)
  excluded_billings = Billing.objects.filter(
    excluded_from=billing, readings__in=readings
  ).distinct()
  for excluded_billing in excluded_billings:
    if not excluded_billing.readings.exclude(id__in=reading_ids).exists():
      excluded_billing.delete()


def _sync_payment(invoice, snapshot, config_cache):
  pending_token = config_cache["invoice_status_pending_token"]
  if not invoice.status or invoice.status.token == pending_token:
    return None

  direct_debit_token = config_cache["direct_debit_token"]
  payment_status_paid = PaymentStatus.objects.get(
    token=config_cache["payment_status_paid_token"]
  )
  payment_balance = PaymentType.objects.get(token="BALANCE")

  Payment.objects.filter(invoice=invoice).delete()

  remittance_date = _get_remittance_date(invoice)
  base_date = _parse_date(invoice.due_date)
  base_send_at = _parse_date(invoice.send_at)
  if not invoice.due_date:
    base_date = base_date + relativedelta(months=1)

  payment_date = base_date
  if remittance_date:
    last_day_of_month = calendar.monthrange(base_date.year, base_date.month)[1]
    remittance_day = min(remittance_date, last_day_of_month)
    if remittance_day > base_date.day:
      payment_date = datetime.date(base_date.year, base_date.month, remittance_day)

  total_final_value = invoice.total_final or 0
  total_paid = (
    check_piggy_bank(invoice, total_final_value, True) if total_final_value > 0 else 0
  )
  invoice.left_to_pay = float(total_final_value) - float(total_paid)
  invoice.save(update_fields=["left_to_pay"])

  if ((invoice.left_to_pay != 0) ^ (invoice.total_final != 0)) and not invoice.is_suppressed:
    return None

  if invoice.left_to_pay != 0:
    payment_status = PaymentStatus.objects.get(
      token=get_payment_status_token_for_invoice_status(invoice.status.token)
    )
  else:
    payment_status = payment_status_paid

  preserved_payment = snapshot.get("payment") or {}
  payment_token = preserved_payment.get("token") or f"{invoice.token}01"

  payment = Payment.objects.create(
    token=payment_token,
    name=invoice.title_final,
    invoice=invoice,
    contract=_get_invoice_contract(invoice),
    customer_final=invoice.customer_final,
    customer_token_final=invoice.customer_token_final,
    payer_final=invoice.payer_final,
    payer_token_final=invoice.payer_token_final,
    amount=invoice.total_final - total_paid if invoice.total_final else 0,
    payment_type=(
      invoice.payment_type_final
      if invoice.left_to_pay != 0
      else payment_balance.name
    ),
    payment_type_token=(
      payment_balance.token
      if invoice.left_to_pay == 0
      else invoice.payment_type_token_final
    ),
    payment_bank=(
      invoice.payment_bank_final
      if invoice.payment_bank_final and invoice.left_to_pay != 0
      else None
    ),
    payment_swift=(
      invoice.payment_swift_final
      if invoice.payment_swift_final and invoice.left_to_pay != 0
      else None
    ),
    address_final=invoice.address_final,
    location_final=invoice.location_final,
    due_date=preserved_payment.get("due_date") or base_date,
    status=payment_status,
    payment_date=(
      preserved_payment.get("payment_date")
      if preserved_payment.get("payment_date")
      else (
        invoice.issue_date
        if invoice.left_to_pay != 0
        else (
          payment_date
          if invoice.payment_type_token_final == direct_debit_token
          else None
        )
      )
    ),
    paid_at=preserved_payment.get("paid_at"),
    sent_date=preserved_payment.get("sent_date"),
    is_active=preserved_payment.get("is_active", True),
  )
  return payment


def _build_config_cache():
  tokens = [
    "invoice_status_pending_token",
    "direct_debit_token",
    "payment_status_paid_token",
  ]
  return {token: ConfigProject.objects.get(token=token).value for token in tokens}


def recalculate_invoice_preserving_identity(invoice_id, config_cache, regenerate_pdf=False):
  with transaction.atomic():
    original = (
      Invoice.objects.select_related(
        "billing", "billing__biller", "contract", "status", "batch"
      )
      .prefetch_related("readings", "readings__modified_readings")
      .get(id=invoice_id)
    )

    original_readings = list(original.readings.all())
    if not original_readings:
      raise ValueError(f"La factura {invoice_id} no té lectures associades")
    if not original.contract_id:
      raise ValueError(f"La factura {invoice_id} no té contracte associat")

    readings = _resolve_readings(original_readings)
    billing = original.billing
    _prepare_readings_billing(billing, readings)

    snapshot = _snapshot_invoice(original)
    billing_batch = original.batch
    title = billing.name if billing else original.title
    period_months = _get_period_months(original)
    contract = original.contract

    extra_payment_data = {}
    if original.issue_date:
      extra_payment_data["issue_date"] = original.issue_date.strftime("%Y-%m-%d")
    if original.billing_period_days is not None:
      extra_payment_data["period_days"] = original.billing_period_days
    if original.billing_period_month is not None:
      extra_payment_data["period_month"] = original.billing_period_month
    if original.billing_period_year is not None:
      extra_payment_data["period_year"] = original.billing_period_year

    temp_invoice = generate_consumption_invoice_multiple(
      contract,
      readings,
      title,
      billing=billing,
      billing_batch=billing_batch,
      period_months=period_months,
      extra_payment_data=extra_payment_data or None,
    )
    if not temp_invoice:
      raise ValueError(
        f"No s'ha pogut generar el recàlcul per a la factura id {invoice_id}"
      )

    _apply_recalculation_to_invoice(original, temp_invoice)
    original.refresh_from_db()

    payment = _sync_payment(original, snapshot, config_cache)

    warning = _get_invoice_warning(original, [contract])
    original.warning = warning
    original.save(update_fields=["warning"])

    if regenerate_pdf:
      from billing.views.invoice_pdf_view import generate_report_invoice_pdf

      generate_report_invoice_pdf(original, config_cache=config_cache)

    return {
      "invoice": original,
      "payment": payment,
      "invoice_id": snapshot["original_id"],
      "old_total": snapshot["original_total"],
      "new_total": original.total_final,
    }


class Command(BaseCommand):
  help = (
    "Recalcula les factures d'un Billing substituint el contingut de cada factura "
    "(mateix id, serie_final i data d'emissió), incloses les dades estàtiques de "
    "client, pagador i adreça. Actualitza pagament si canvia el total."
  )

  def add_arguments(self, parser):
    parser.add_argument(
      "--billing-id",
      type=int,
      required=True,
      help="ID del Billing.",
    )
    parser.add_argument(
      "--invoice-ids",
      type=str,
      default=None,
      help="IDs de factura opcionals separats per comes (ex: 10,11,12).",
    )
    parser.add_argument(
      "--dry-run",
      action="store_true",
      help="Mostra què es faria sense aplicar canvis.",
    )
    parser.add_argument(
      "--list-invoices",
      action="store_true",
      help="Amb --dry-run, llista cada factura.",
    )
    parser.add_argument(
      "--regenerate-pdf",
      action="store_true",
      help="Regenera el PDF després del recàlcul.",
    )

  def handle(self, *args, **options):
    billing_id = options["billing_id"]
    dry_run = options["dry_run"]
    regenerate_pdf = options["regenerate_pdf"]
    invoice_ids = self._parse_invoice_ids(options.get("invoice_ids"))

    if not Billing.objects.filter(id=billing_id).exists():
      raise CommandError(f"No s'ha trobat cap Billing amb id={billing_id}.")

    invoices = (
      Invoice.objects.filter(billing_id=billing_id, is_active=True, is_excluded=False)
      .select_related("status", "contract")
      .prefetch_related("readings")
      .order_by("issue_date", "id")
    )
    if invoice_ids:
      invoices = invoices.filter(id__in=invoice_ids)

    if not invoices.exists():
      raise CommandError(f"No hi ha factures per processar al billing id={billing_id}.")

    self.stdout.write("")
    self.stdout.write(self.style.MIGRATE_HEADING("--- Recalcular factures (preservant serie_final) ---"))
    self.stdout.write(f"Billing id: {billing_id}")
    if invoice_ids:
      self.stdout.write(f"Filtre invoice-ids: {invoice_ids}")
    if dry_run:
      self.stdout.write(self.style.WARNING("MODE DRY-RUN"))
    self.stdout.write("")

    if dry_run:
      processed = 0
      skipped = 0
      if options["list_invoices"]:
        self.stdout.write("Factures:")
      for invoice in invoices:
        can_process = invoice.readings.exists() and invoice.contract_id
        if not can_process:
          skipped += 1
          label = "OMESA"
        else:
          processed += 1
          label = "RECALCULAR"
        if options["list_invoices"]:
          status_t = invoice.status.token if invoice.status else "-"
          self.stdout.write(
            f"  [{label}] id={invoice.id} serie={invoice.serie_final} "
            f"issue_date={invoice.issue_date} total={invoice.total_final} status={status_t}"
          )
      self.stdout.write("")
      self.stdout.write(f"Es recalcularien: {processed}")
      self.stdout.write(f"Es saltarien: {skipped}")
      return

    config_cache = _build_config_cache()
    invoice_id_list = list(invoices.values_list("id", flat=True))
    ok = 0
    skipped = 0
    errors = []

    disconnect_payment_signals()
    try:
      for invoice_id in invoice_id_list:
        invoice = Invoice.objects.filter(id=invoice_id).prefetch_related("readings").first()
        if not invoice or not invoice.readings.exists() or not invoice.contract_id:
          skipped += 1
          continue
        try:
          result = recalculate_invoice_preserving_identity(
            invoice_id,
            config_cache=config_cache,
            regenerate_pdf=regenerate_pdf,
          )
          ok += 1
          old_total = result["old_total"]
          new_total = result["new_total"]
          total_msg = (
            f"total {old_total} -> {new_total}"
            if old_total != new_total
            else f"total {new_total} (sense canvi)"
          )
          payment_msg = "pagament actualitzat" if result["payment"] else "sense pagament"
          self.stdout.write(
            self.style.SUCCESS(
              f"  OK id={result['invoice_id']} "
              f"serie={result['invoice'].serie_final} issue_date={result['invoice'].issue_date} "
              f"{total_msg}, {payment_msg}"
            )
          )
        except Exception as exc:
          errors.append({"invoice_id": invoice_id, "error": str(exc)})
          self.stdout.write(self.style.ERROR(f"  ERROR id={invoice_id}: {exc}"))
    finally:
      reconnect_payment_signals()

    self.stdout.write("")
    self.stdout.write(self.style.SUCCESS(f"Recalculades: {ok}"))
    self.stdout.write(f"Omeses: {skipped}")
    if errors:
      raise CommandError(f"Han fallat {len(errors)} factura(es).")

  def _parse_invoice_ids(self, raw_invoice_ids):
    if not raw_invoice_ids:
      return None
    try:
      parsed = [
        int(value.strip())
        for value in raw_invoice_ids.split(",")
        if value.strip()
      ]
    except ValueError as exc:
      raise CommandError(
        "Format invàlid per --invoice-ids. Exemple: --invoice-ids 10,11,12"
      ) from exc
    if not parsed:
      raise CommandError("No s'han indicat IDs de factura vàlids.")
    return parsed
