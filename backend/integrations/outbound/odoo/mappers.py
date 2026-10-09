from decimal import Decimal

from billing.models import Invoice, InvoiceLineItem, PaymentMovement
from coredata.utils.other_utils import round_ceil

from .exceptions import OdooMappingError


def _to_float(value):
    if value is None:
        return 0.0
    return float(value)


def _round2(value):
    return round(_to_float(value), 2)


def resolve_partner_aqua_id(invoice: Invoice) -> str:
    """
    Àncora del partner a Odoo.

    Si la factura té contracte (directe, via sol·licitud o via baixa), l'aqua_id
    és el token del contracte. Si no, és customer_token_final.
    contract_request.token coincideix amb el token del contracte.
    """
    if invoice.contract and invoice.contract.token:
        return invoice.contract.token
    if invoice.contract_request and invoice.contract_request.token:
        return invoice.contract_request.token
    termination = invoice.contract_termination
    if termination and termination.contract and termination.contract.token:
        return termination.contract.token
    return invoice.customer_token_final or ""


def resolve_partner(invoice: Invoice) -> dict:
    if not invoice.customer_final:
        raise OdooMappingError(
            f"La factura {invoice.token} no té customer_final (nom del partner)."
        )
    if not invoice.customer_token_final:
        raise OdooMappingError(
            f"La factura {invoice.token} no té customer_token_final (vat del partner)."
        )

    return {
        "aqua_id": resolve_partner_aqua_id(invoice),
        "name": invoice.customer_final,
        "vat": resolve_partner_vat(invoice),
    }


def resolve_partner_vat(invoice: Invoice) -> str:
    """NIF/CIF del partner a Odoo: sempre customer_token_final."""
    return invoice.customer_token_final or ""


def resolve_journal(invoice: Invoice) -> dict:
    serie = invoice.serie
    if not serie or not serie.token:
        raise OdooMappingError(
            f"La factura {invoice.token} no té sèrie (billing.InvoiceSerie) per al diari Odoo."
        )
    return {
        "aqua_id": serie.token,
        "name": serie.name or serie.token,
    }


def resolve_payment_mode(payment_type_token: str, payment_type_name: str = "") -> dict:
    if not payment_type_token:
        raise OdooMappingError("Cal payment_type_token per al mode de pagament Odoo.")
    return {
        "id": payment_type_token,
        "name": payment_type_name or payment_type_token,
    }


def map_line_item(line: InvoiceLineItem) -> dict:
    product = line.product
    if not product or not product.token:
        raise OdooMappingError(
            f"La línia {line.id} de factura no té producte amb token (pricing.Product)."
        )

    tax_token = line.tax.token if line.tax and line.tax.token else None
    if not tax_token:
        raise OdooMappingError(
            f"La línia {line.id} no té impost amb token (pricing.Tax)."
        )

    return {
        "product_id": {
            "aqua_id": product.token,
            "name": line.product_name or product.name or product.token,
        },
        "name": line.name or line.description or line.product_name or product.name,
        "quantity": _to_float(line.units),
        "price_unit": line.price_unit,
        "discount": 0.0,
        "tax_ids": [tax_token],
        "price_subtotal": round_ceil(line.price),
        "price_tax": round_ceil(line.tax_price),
        "price_total": round_ceil(line.total),
    }


def map_invoice_to_odoo(invoice: Invoice) -> dict:
    if not invoice.token:
        raise OdooMappingError("La factura no té token (aqua_id).")
    if not invoice.serie_final:
        raise OdooMappingError(f"La factura {invoice.token} no té serie_final (name Odoo).")
    if not invoice.issue_date:
        raise OdooMappingError(f"La factura {invoice.token} no té issue_date.")
    if invoice.subtotal_final is None or invoice.total_final is None:
        raise OdooMappingError(f"La factura {invoice.token} no té totals finals.")

    lines = invoice.line_items.filter(is_active=True).select_related(
        "product", "tax"
    )
    if not lines.exists():
        raise OdooMappingError(f"La factura {invoice.token} no té línies actives.")

    move_type = "out_refund" if invoice.parent_invoice_id else "out_invoice"
    amount_untaxed = round_ceil(invoice.subtotal_final)
    amount_total = round_ceil(invoice.total_final)
    amount_tax = round_ceil(Decimal(str(amount_total)) - Decimal(str(amount_untaxed)))

    payload = {
        "aqua_id": invoice.token,
        "move_type": move_type,
        "name": invoice.serie_final,
        "invoice_date": invoice.issue_date.isoformat(),
        "partner_id": resolve_partner(invoice),
        "journal_id": resolve_journal(invoice),
        "payment_mode_id": resolve_payment_mode(
            invoice.payment_type_token_final or "",
            invoice.payment_type_final or "",
        ),
        "invoice_line_ids": [map_line_item(line) for line in lines],
        "amount_untaxed": amount_untaxed,
        "amount_tax": amount_tax,
        "amount_total": amount_total,
    }

    if invoice.due_date:
        payload["invoice_date_due"] = invoice.due_date.isoformat()

    if invoice.parent_invoice_id:
        if not invoice.parent_invoice or not invoice.parent_invoice.token:
            raise OdooMappingError(
                f"La rectificativa {invoice.token} no té parent_invoice.token."
            )
        payload["reversed_aqua_id"] = invoice.parent_invoice.token

    return payload


def resolve_payment_journal(movement: PaymentMovement) -> dict | None:
    company_bank = None
    if movement.payment_remittance and movement.payment_remittance.company_bank:
        company_bank = movement.payment_remittance.company_bank
    elif movement.payment and movement.payment.invoice:
        company_bank = movement.payment.invoice.payment_company_bank

    if not company_bank or not company_bank.token:
        return None

    bank_name = company_bank.token
    if company_bank.bank and company_bank.bank.name:
        bank_name = company_bank.bank.name

    return {
        "aqua_id": company_bank.token,
        "name": bank_name,
    }


def resolve_movement_invoice(movement: PaymentMovement) -> Invoice | None:
    if movement.payoff_invoice:
        return movement.payoff_invoice
    if movement.payment and movement.payment.invoice:
        return movement.payment.invoice
    return None


def is_movement_pushable(movement: PaymentMovement) -> bool:
    if not movement.is_active:
        return False
    if movement.is_positive is None:
        return False
    if not movement.payment:
        return False
    if movement.payment.amount is None:
        return False
    return True


def movement_signed_amount(movement: PaymentMovement) -> float:
    """Import amb signe: positiu si és cobrament, negatiu si és devolució."""
    amount = round_ceil(abs(movement.payment.amount))
    if movement.is_positive is False:
        return -amount
    return amount


def resolve_movement_partner(movement: PaymentMovement, invoice: Invoice | None) -> dict:
    if invoice:
        return resolve_partner(invoice)

    payment = movement.payment
    aqua_id = payment.customer_token_final
    name = payment.customer_final
    if not aqua_id or not name:
        raise OdooMappingError(
            f"El moviment {movement.token or movement.id} no té factura ni "
            "customer_token_final/customer_final al pagament."
        )

    vat = ""
    contract = payment.contract
    if contract and contract.company and contract.company.vat:
        vat = contract.company.vat
    elif payment.payer_token_final:
        vat = payment.payer_token_final
    else:
        vat = aqua_id

    return {
        "aqua_id": aqua_id,
        "name": name,
        "vat": vat,
    }


def build_movement_memo(movement: PaymentMovement, invoice: Invoice | None) -> str:
    label = "Cobrament rebut"
    if invoice and invoice.serie_final:
        label = f"{label} {invoice.serie_final}"
    parts = [label]
    if movement.payment_remittance and movement.payment_remittance.token:
        parts.append(f"remesa {movement.payment_remittance.token}")
    return " - ".join(parts)


def map_payment_movement_to_odoo(movement: PaymentMovement) -> dict:
    if not is_movement_pushable(movement):
        raise OdooMappingError(
            f"El moviment {movement.id} no és enviable a Odoo "
            "(cal is_active, is_positive informat i payment amb import)."
        )
    if not movement.token:
        raise OdooMappingError(f"El moviment {movement.id} no té token (aqua_id).")
    if not movement.movement_date:
        raise OdooMappingError(f"El moviment {movement.token} no té movement_date.")

    payment = movement.payment
    invoice = resolve_movement_invoice(movement)

    payment_type = movement.payment_type
    payment_type_token = (
        payment_type.token if payment_type else payment.payment_type_token
    )
    payment_type_name = payment_type.name if payment_type else payment.payment_type

    payload = {
        "aqua_id": movement.token,
        "payment_type": "inbound",
        "partner_id": resolve_movement_partner(movement, invoice),
        "amount": movement_signed_amount(movement),
        "date": movement.movement_date.isoformat(),
        "memo": build_movement_memo(movement, invoice),
        "payment_mode_id": resolve_payment_mode(
            payment_type_token or "",
            payment_type_name or "",
        ),
        "reconcile": {
            "invoice_aqua_id": invoice.token if invoice and invoice.token else "",
        },
    }

    journal = resolve_payment_journal(movement)
    if journal:
        payload["journal_id"] = journal

    return payload
