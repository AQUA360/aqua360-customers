"""Dades de cada avís i funcions que es criden des del codi de negoci.

Avisos (event_type):
- contract.created: contracte nou en confirmar una sol·licitud d'alta.
- contract_termination.confirmed: el contracte passa realment a baixa.
- contract_termination.cancelled: es desfà una baixa.
- invoice.issued: factura solta que rep el número legal (no pressupostos).
- billing.issued: facturació massiva confirmada, amb les factures en paquets.
- contract_request.cancelled: una sol·licitud d'alta passa a anul·lada (senyal, vegeu signals.py).
- invoice.paid, invoice.returned, invoice.expired, invoice.cancelled: canvis d'estat
  de pagament de les factures, detectats per una tasca periòdica (invoice_status.py).

Cada registre porta l'id intern (estable) i el codi: en un canvi de titular que
conserva el codi, el contracte antic canvia de codi i només l'id el segueix.
"""
import math
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from coredata.models import ConfigProject

from . import dispatcher
from .dispatcher import emit, webhooks_configured, webhooks_enabled

CONTRACT_CREATED = "contract.created"
CONTRACT_TERMINATION_CONFIRMED = "contract_termination.confirmed"
CONTRACT_TERMINATION_CANCELLED = "contract_termination.cancelled"
INVOICE_ISSUED = "invoice.issued"
BILLING_ISSUED = "billing.issued"
CONTRACT_REQUEST_CANCELLED = "contract_request.cancelled"


# --- Peces comunes ---------------------------------------------------------

def _date(value):
    return value.isoformat() if value else None


def _amount(value):
    return str(Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _token_name(obj):
    return {"token": obj.token, "name": obj.name} if obj else None


def _contract_ref(contract):
    return {"id": contract.id, "code": contract.token} if contract else None


def _person(person):
    if not person:
        return None
    return {"id": person.id, "name": str(person).strip(), "tax_id": person.token}


def _config_value(token):
    return ConfigProject.objects.filter(token=token).values_list("value", flat=True).first()


# --- Contractes ------------------------------------------------------------

def contract_created_data(contract):
    contract_request = contract.contract_request
    request_data = None
    if contract_request:
        previous_contract = None
        if contract_request.is_change_of_name:
            termination = (
                contract_request.contract_termination_requests.select_related("contract")
                .exclude(contract__isnull=True)
                .first()
            )
            previous_contract = _contract_ref(termination.contract) if termination else None
        request_data = {
            "id": contract_request.id,
            "code": contract_request.token,
            "is_change_of_name": bool(contract_request.is_change_of_name),
            "previous_contract": previous_contract,
        }

    supply_point = contract.supply_point_default
    return {
        "contract": {
            "id": contract.id,
            "code": contract.token,
            # Si la sol·licitud no en duia, el dia que s'ha creat el contracte
            "registration_date": _date(
                contract.registration_date or (timezone.localdate(contract.created_at) if contract.created_at else None)
            ),
        },
        "contract_request": request_data,
        "holder": _person(contract.holder),
        "supply_point": {
            "id": supply_point.id,
            "code": supply_point.token,
            "address": str(supply_point.address) if supply_point.address else None,
        } if supply_point else None,
    }


def _termination_is_change_of_name(termination_request):
    return termination_request.contract_requests_termination_requests.filter(is_change_of_name=True).exists()


def contract_termination_confirmed_data(contract, termination_request):
    return {
        "contract": {
            "id": contract.id,
            "code": contract.token,
            "termination_date": _date(contract.termination_date),
        },
        "termination_request": {
            "id": termination_request.id,
            "code": termination_request.token,
            "type": _token_name(termination_request.type),
            "is_change_of_name": _termination_is_change_of_name(termination_request),
        } if termination_request else None,
        "holder": _person(contract.holder),
    }


def contract_termination_cancelled_data(contract, termination_request):
    return {
        "contract": _contract_ref(contract),
        "termination_request": {
            "id": termination_request.id,
            "code": termination_request.token,
        } if termination_request else None,
    }


def emit_contract_created(contract):
    # Un contracte només es crea una vegada: la clau evita repetir-ne l'avís
    return emit(
        CONTRACT_CREATED, "contract", contract.id,
        lambda: contract_created_data(contract),
        dedupe_key=f"{CONTRACT_CREATED}:{contract.id}",
    )


def emit_contract_termination_confirmed(contract, termination_request):
    # Sense clau: una baixa es pot desfer i tornar a fer. Qui la crida només ho fa
    # quan el contracte passa a baixa (vegeu mark_contract_terminated).
    return emit(
        CONTRACT_TERMINATION_CONFIRMED, "contract", contract.id,
        lambda: contract_termination_confirmed_data(contract, termination_request),
    )


def emit_contract_termination_cancelled(contract, termination_request):
    return emit(
        CONTRACT_TERMINATION_CANCELLED, "contract", contract.id,
        lambda: contract_termination_cancelled_data(contract, termination_request),
    )


def contract_request_cancelled_data(contract_request):
    return {
        "contract_request": {"id": contract_request.id, "code": contract_request.token},
        "status": _token_name(contract_request.status),
    }


def emit_contract_request_cancelled(contract_request):
    """La sol·licitud d'alta passa a l'estat anul·lat. Sense clau: es pot reobrir i
    tornar a anul·lar. Qui la crida (signals.py) només ho fa quan l'estat canvia."""
    cancel_token = _config_value("contract_request_cancel_token")
    if not cancel_token or not contract_request.status or contract_request.status.token != cancel_token:
        return None
    return emit(
        CONTRACT_REQUEST_CANCELLED, "contract_request", contract_request.id,
        lambda: contract_request_cancelled_data(contract_request),
    )


# --- Factures --------------------------------------------------------------

def _corrected_invoice(invoice, cache=None):
    """Factura que corregeix (rectificativa o abonament), si n'hi ha."""
    from billing.models import Invoice

    token = invoice.refactored_token or invoice.return_token
    if not token:
        return None
    if cache is not None and token in cache:
        return cache[token]
    original = Invoice.objects.filter(token=token).exclude(id=invoice.id).values("id", "serie_final").first()
    result = {"id": original["id"], "number": original["serie_final"]} if original else None
    if cache is not None:
        cache[token] = result
    return result


def invoice_data(invoice, direct_debit_token=None, line_items=None, corrected_cache=None):
    from billing.utils.invoice_service import get_totals

    subtotal, taxes, taxes_base, total = get_totals(invoice, line_items=line_items)
    holder_id = invoice.person_id or (invoice.contract.holder_id if invoice.contract else None)
    return {
        "id": invoice.id,
        "token": invoice.token,
        "number": invoice.serie_final,
        "serie": invoice.serie_token_final,
        "type": _token_name(invoice.type),
        "category": _token_name(invoice.category),
        "is_rectifying": bool(invoice.refactored_token),
        "corrects": _corrected_invoice(invoice, corrected_cache),
        "issue_date": _date(invoice.issue_date),
        "due_date": _date(invoice.due_date),
        "period": {
            "year": invoice.billing_period_year,
            "month": invoice.billing_period_month,
            "days": invoice.billing_period_days,
        },
        "contract": _contract_ref(invoice.contract),
        "holder": {"id": holder_id} if holder_id else None,
        "amounts": {
            "subtotal": _amount(subtotal),
            "taxes": [
                {"rate": rate, "base": _amount(taxes_base.get(rate)), "amount": _amount(amount)}
                for rate, amount in sorted(taxes.items())
            ],
            "total": _amount(total),
            "currency": "EUR",
        },
        "direct_debit": bool(direct_debit_token) and invoice.payment_type_token_final == direct_debit_token,
    }


def is_budget(invoice):
    budget_token = _config_value("invoice_type_budget_token")
    if not budget_token:
        return False
    return (invoice.type is not None and invoice.type.token == budget_token) or invoice.type_final == budget_token


def emit_invoice_issued(invoice):
    """Factura solta que acaba de rebre el número legal. Les de la facturació
    massiva no passen per aquí: van agrupades a billing.issued."""
    if not webhooks_enabled() or is_budget(invoice):
        return None
    return emit(
        INVOICE_ISSUED, "invoice", invoice.id,
        lambda: invoice_data(invoice, _config_value("direct_debit_token")),
        dedupe_key=f"{INVOICE_ISSUED}:{invoice.id}",
    )


def emit_billing_issued(billing, invoice_ids):
    """Facturació massiva confirmada: un avís per paquet de factures
    (WEBHOOKS_BILLING_CHUNK_SIZE), en lloc d'un per factura."""
    from billing.models import Invoice, InvoiceLineItem

    if not webhooks_enabled() or not invoice_ids:
        return []

    budget_token = _config_value("invoice_type_budget_token")
    direct_debit_token = _config_value("direct_debit_token")
    invoices = (
        Invoice.objects.filter(id__in=invoice_ids)
        .select_related("type", "category", "contract")
        .prefetch_related(Prefetch("line_items", queryset=InvoiceLineItem.objects.filter(is_active=True)))
        .order_by("id")
    )
    if budget_token:
        invoices = invoices.exclude(type__token=budget_token).exclude(type_final=budget_token)
    ids = list(invoices.values_list("id", flat=True))
    if not ids:
        return []

    size = max(1, settings.WEBHOOKS_BILLING_CHUNK_SIZE)
    parts = math.ceil(len(ids) / size)
    corrected_cache = {}
    events = []
    for index in range(parts):
        chunk_ids = ids[index * size:(index + 1) * size]

        def build(chunk_ids=chunk_ids, part=index + 1):
            return {
                "billing": {"id": billing.id, "name": billing.name},
                "part": part,
                "parts": parts,
                "invoices": [
                    invoice_data(invoice, direct_debit_token, list(invoice.line_items.all()), corrected_cache)
                    for invoice in invoices.filter(id__in=chunk_ids)
                ],
            }

        # La clau inclou les factures del paquet: tornar a processar la mateixa
        # facturació amb les mateixes factures no en repeteix l'avís.
        event = emit(
            BILLING_ISSUED, "billing", billing.id, build,
            dedupe_key=f"{BILLING_ISSUED}:{billing.id}:{chunk_ids[0]}-{chunk_ids[-1]}:{len(chunk_ids)}",
            schedule=False,
        )
        if event:
            events.append(event)

    if events and webhooks_configured():
        from django.db import transaction
        transaction.on_commit(dispatcher.schedule_send)
    return events
