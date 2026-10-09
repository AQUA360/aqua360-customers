from billing.models import Invoice, PaymentMovement

from .client import OdooClient
from .exceptions import OdooMappingError
from .mappers import map_invoice_to_odoo, map_payment_movement_to_odoo


def push_invoice(invoice_id: int, *, client=None, dry_run=False) -> dict:
    invoice = Invoice.objects.select_related(
        "serie",
        "parent_invoice",
        "company",
        "contract__company",
        "payment_type",
    ).prefetch_related(
        "line_items__product",
        "line_items__tax",
    ).get(pk=invoice_id)

    payload = map_invoice_to_odoo(invoice)
    if dry_run:
        return payload

    odoo_client = client or OdooClient()
    return odoo_client.push_invoice(payload)


def push_payment_movement(movement_id: int, *, client=None, dry_run=False) -> dict:
    movement = PaymentMovement.objects.select_related(
        "payment__invoice__serie",
        "payment__invoice__company",
        "payment__invoice__contract__company",
        "payment__invoice__parent_invoice",
        "payment__invoice__payment_company_bank__bank",
        "payment__contract__company",
        "payment_type",
        "payoff_invoice__serie",
        "payoff_invoice__company",
        "payoff_invoice__contract__company",
        "payment_remittance__company_bank__bank",
    ).get(pk=movement_id)

    payload = map_payment_movement_to_odoo(movement)
    if dry_run:
        return payload

    odoo_client = client or OdooClient()
    return odoo_client.push_payment(payload)


def build_invoice_payload(invoice_id: int) -> dict:
    """Retorna el JSON Odoo sense enviar-lo (útil per validació i tests)."""
    try:
        return push_invoice(invoice_id, dry_run=True)
    except OdooMappingError:
        raise


def build_payment_movement_payload(movement_id: int) -> dict:
    """Retorna el JSON Odoo sense enviar-lo (útil per validació i tests)."""
    try:
        return push_payment_movement(movement_id, dry_run=True)
    except OdooMappingError:
        raise
