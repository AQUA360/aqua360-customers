from django.db import transaction

from billing.models import Invoice, InvoiceWarning, Reading, Billing
from billing.utils.invoice_service import generate_consumption_invoice_multiple
from coredata.models import ConfigProject
from statistics.utils.billing_amount_average import is_high_amount_for_period


PERIOD_MONTHS_MAP = {
    "trimestral": 90,
    "semestral": 180,
    "bimestral": 60,
    "quadrimestral": 120,
    "anual": 360,
    "mensual": 30,
}


def _assert_invoice_is_recalculable(invoice):
    """
    Bloqueja el recàlcul d'una factura ja finalitzada per via externa (confirmada,
    pagada, vençuda, etc.): esborrar-la i regenerar-ne una de nova en perdria la
    confirmació/pagament ja fet.
    """
    prefactura_token = ConfigProject.objects.get(token='invoice_status_pending_token').value
    if not invoice.status or invoice.status.token != prefactura_token:
        raise ValueError(
            f"Invoice {invoice.id} is no longer a Pre-factura "
            f"(status: {invoice.status.name if invoice.status else 'None'}) and cannot be recalculated"
        )


def _get_period_months(invoice):
    if not invoice.billing or not invoice.billing.biller:
        return None
    period_type = invoice.billing.biller.period_type
    period_days = PERIOD_MONTHS_MAP.get(period_type)
    if not period_days:
        return None
    return period_days / 30


def _get_invoice_warning(invoice, contracts):
    warning = None

    invoice_warning_negative_token = ConfigProject.objects.get(token="invoice_warning_negative").value
    invoice_warning_negative = InvoiceWarning.objects.get(token=invoice_warning_negative_token)

    invoice_warning_zero_token = ConfigProject.objects.get(token="invoice_warning_zero").value
    invoice_warning_zero = InvoiceWarning.objects.get(token=invoice_warning_zero_token)

    invoice_warning_bank_missing_token = ConfigProject.objects.get(token="invoice_warning_bank_missing").value
    invoice_warning_bank_missing = InvoiceWarning.objects.get(token=invoice_warning_bank_missing_token)

    invoice_warning_payment_missing_token = ConfigProject.objects.get(token="invoice_warning_payment_missing").value
    invoice_warning_payment_missing = InvoiceWarning.objects.get(token=invoice_warning_payment_missing_token)

    invoice_warning_simplified_over_400_token = ConfigProject.objects.get(token="invoice_warning_simplified_over_400").value
    invoice_warning_simplified_over_400 = InvoiceWarning.objects.get(token=invoice_warning_simplified_over_400_token)

    invoice_warning_high_amount_token = ConfigProject.objects.get(token="invoice_warning_high_amount").value
    invoice_warning_high_amount = InvoiceWarning.objects.get(token=invoice_warning_high_amount_token)

    if invoice.total_final <= 0:
        warning = invoice_warning_negative
    elif invoice.total_final == 0:
        warning = invoice_warning_zero
    elif invoice.payment_type is None:
        warning = invoice_warning_payment_missing
    elif invoice.payment_type.token == "DIRECT_DEBIT" and invoice.payment_bank is None:
        warning = invoice_warning_bank_missing
    elif invoice.simplified and invoice.total_final >= 400:
        warning = invoice_warning_simplified_over_400
    elif invoice.total_final:
        if is_high_amount_for_period(invoice.total_final, contracts, invoice.billing_period_year, invoice.billing_period_month, exclude_invoice_id=invoice.id):
            warning = invoice_warning_high_amount

    return warning


def delete_and_recalculate_invoice(invoice_id):
    with transaction.atomic():
        original_invoice = (
            Invoice.objects.select_related("billing", "billing__biller", "contract")
            .prefetch_related("readings", "readings__contract")
            .get(id=invoice_id)
        )
        _assert_invoice_is_recalculable(original_invoice)

        readings = list(original_invoice.readings.all())
        if not readings:
            raise ValueError(f"Invoice {invoice_id} has no readings associated")

        contracts = []
        seen_contract_ids = set()
        for reading in readings:
            if reading.contract_id and reading.contract_id not in seen_contract_ids:
                contracts.append(reading.contract)
                seen_contract_ids.add(reading.contract_id)

        if not contracts:
            raise ValueError(f"Invoice {invoice_id} has no contracts associated via readings")

        billing = original_invoice.billing
        title = billing.name if billing else original_invoice.title
        period_months = _get_period_months(original_invoice)

        original_invoice.delete()

        new_invoice = generate_consumption_invoice_multiple(
            contracts,
            readings,
            title,
            billing=billing,
            period_months=period_months,
        )

        if not new_invoice:
            raise ValueError(f"Invoice {invoice_id} recalculation did not generate a new invoice")

        warning = _get_invoice_warning(new_invoice, contracts)
        if warning:
            new_invoice.warning = warning
            new_invoice.save(update_fields=["warning"])

        return new_invoice

def recalculate_invoice_smart(invoice_id):
    with transaction.atomic():
        original_invoice = (
            Invoice.objects.select_related("billing", "billing__biller", "contract")
            .prefetch_related("readings", "readings__contract", "readings__modified_readings")
            .get(id=invoice_id)
        )
        _assert_invoice_is_recalculable(original_invoice)

        original_readings = list(original_invoice.readings.all())
        if not original_readings:
            raise ValueError(f"Invoice {invoice_id} has no readings associated")

        readings = []
        for reading in original_readings:
            if reading.is_control:
                # Look for a non-control modification
                new_reading = reading.modified_readings.filter(is_control=False).first()
                if new_reading:
                    readings.append(new_reading)
                else:
                    # If it's a control reading and has no modifications, check if it's a modification itself
                    # (this handles the case where the linked reading was already a modification but now is also control)
                    readings.append(reading)
            else:
                readings.append(reading)

        contract = original_invoice.contract

        billing = original_invoice.billing
        
        # If the invoice was excluded, move readings back to the original billing
        if billing:
            Reading.objects.filter(id__in=[r.id for r in readings]).update(billing=billing)
            # Find and potentially cleanup excluded billing
            excluded_billings = Billing.objects.filter(excluded_from=billing, readings__in=readings).distinct()
            for ex_billing in excluded_billings:
                if not ex_billing.readings.exclude(id__in=[r.id for r in readings]).exists():
                    ex_billing.delete()

        title = billing.name if billing else original_invoice.title_final
        period_months = _get_period_months(original_invoice)

        original_invoice.delete()

        new_invoice = generate_consumption_invoice_multiple(
            contract,
            readings,
            title,
            billing=billing,
            period_months=period_months,
        )

        if not new_invoice:
            raise ValueError(f"Invoice {invoice_id} recalculation did not generate a new invoice")

        warning = _get_invoice_warning(new_invoice, [contract])
        new_invoice.warning = warning
        new_invoice.save(update_fields=["warning"])


        return new_invoice
