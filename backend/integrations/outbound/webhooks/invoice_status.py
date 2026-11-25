"""Avisos d'estat de pagament de les factures: invoice.paid, invoice.returned,
invoice.expired i invoice.cancelled.

L'estat d'una factura canvia des de molts llocs (senyal del rebut, remeses,
devolucions, venciments, cobrament massiu, anul·lacions...), i alguns fan
update() massius que no passen pels senyals. En lloc d'enganxar cada camí, una
tasca periòdica compara l'estat actual de totes les factures amb la foto del
darrer estat avisat (WebhookInvoiceState) i avisa dels canvis, agrupats en
paquets (WEBHOOKS_BILLING_CHUNK_SIZE) com billing.issued.

- La primera execució (foto buida) fa la foto sense avisar.
- Si una factura canvia dues vegades entre dues execucions, només s'avisa de
  l'estat final.
- Retornada: un rebut actiu de la factura passa a l'estat de rebut retornat. La
  factura no té cap estat «retornada» (torna a Confirmada o Vençuda), per això la
  foto en guarda la marca a part.
- Només s'avisa de factures actives, amb número i que no són pressupostos; la foto, però,
  les inclou totes perquè no es tornin a detectar.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.db import connection, transaction
from django.db.models import DecimalField, Max, OuterRef, Prefetch, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from coredata.models import ConfigProject
from integrations.models import WebhookInvoiceState

from . import dispatcher
from .dispatcher import emit, webhooks_configured, webhooks_enabled

logger = logging.getLogger(__name__)

INVOICE_PAID = "invoice.paid"
INVOICE_RETURNED = "invoice.returned"
INVOICE_EXPIRED = "invoice.expired"
INVOICE_CANCELLED = "invoice.cancelled"

# Clau del bloqueig de PostgreSQL que garanteix una sola comparació alhora
SCAN_LOCK_KEY = 289100001

CONFIG_TOKENS = (
    "invoice_status_paid_token",
    "invoice_status_expired_token",
    "invoice_status_cancelled_token",
    "invoice_status_dropped_token",
    "invoice_type_budget_token",
    "payment_status_paid_token",
    "payment_status_piggy_token",
    "payment_status_returned_token",
    "direct_debit_token",
)


def _config():
    values = dict(ConfigProject.objects.filter(token__in=CONFIG_TOKENS).values_list("token", "value"))
    return {token: values.get(token) for token in CONFIG_TOKENS}


def _tables():
    from billing.models import Invoice, Payment, PaymentStatus

    return {
        "invoice": Invoice._meta.db_table,
        "payment": Payment._meta.db_table,
        "payment_status": PaymentStatus._meta.db_table,
        "state": WebhookInvoiceState._meta.db_table,
    }


def _returned_sql(tables):
    return (
        f"(i.id IN (SELECT p.invoice_id FROM {tables['payment']} p "
        f"WHERE p.is_active AND p.invoice_id IS NOT NULL AND p.status_id IN "
        f"(SELECT ps.id FROM {tables['payment_status']} ps WHERE ps.token = %s)))"
    )


def seed_state(returned_token=None):
    if returned_token is None:
        returned_token = _config()["payment_status_returned_token"]
    tables = _tables()
    returned = _returned_sql(tables) if returned_token else "FALSE"
    params = [returned_token] if returned_token else []
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {tables['state']} (invoice_id, status_id, is_returned, updated_at) "
            f"SELECT i.id, i.status_id, {returned}, NOW() FROM {tables['invoice']} i "
            f"ON CONFLICT (invoice_id) DO NOTHING",
            params,
        )
        return cursor.rowcount


def reset_state():
    with transaction.atomic():
        WebhookInvoiceState.objects.all().delete()
        return seed_state()


def _changed_rows(config, limit):
    tables = _tables()
    returned_token = config["payment_status_returned_token"]
    returned = _returned_sql(tables) if returned_token else "FALSE"
    params = [returned_token] * 2 if returned_token else []
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT i.id, i.status_id, {returned} AS is_returned, "
            f"s.invoice_id IS NOT NULL AS known, s.status_id, s.is_returned "
            f"FROM {tables['invoice']} i "
            f"LEFT JOIN {tables['state']} s ON s.invoice_id = i.id "
            f"WHERE s.invoice_id IS NULL OR s.status_id IS DISTINCT FROM i.status_id "
            f"OR s.is_returned <> {returned} "
            f"ORDER BY i.id LIMIT %s",
            params + [limit],
        )
        return [
            {
                "invoice_id": row[0],
                "status_id": row[1],
                "is_returned": bool(row[2]),
                "known": row[3],
                "previous_status_id": row[4],
                "previous_is_returned": bool(row[5]),
            }
            for row in cursor.fetchall()
        ]


def classify(row, status_ids):
    previous_is_returned = row["previous_is_returned"] if row["known"] else False
    if row["is_returned"] and not previous_is_returned:
        return INVOICE_RETURNED
    if row["known"] and row["previous_status_id"] == row["status_id"]:
        return None
    return status_ids.get(row["status_id"])


def _status_ids(config):
    from billing.models import InvoiceStatus

    by_token = {
        config["invoice_status_paid_token"]: INVOICE_PAID,
        config["invoice_status_expired_token"]: INVOICE_EXPIRED,
        # Abonada (tenia cobraments) o anul·lada (sense cobrar): totes dues
        # deixen la factura sense deute; `status` diu quina
        config["invoice_status_cancelled_token"]: INVOICE_CANCELLED,
        config["invoice_status_dropped_token"]: INVOICE_CANCELLED,
    }
    by_token.pop(None, None)
    return {
        status_id: by_token[token]
        for status_id, token in InvoiceStatus.objects.filter(token__in=by_token).values_list("id", "token")
    }


def _notifiable_ids(invoice_ids, budget_token):
    from billing.models import Invoice

    invoices = (
        Invoice.objects.filter(id__in=invoice_ids, is_active=True)
        .exclude(serie_final__isnull=True)
        .exclude(serie_final="")
    )
    if budget_token:
        invoices = invoices.exclude(type__token=budget_token).exclude(type_final=budget_token)
    return set(invoices.values_list("id", flat=True))


def _invoices_queryset(invoice_ids, config):
    from billing.models import Invoice, InvoiceLineItem, Payment
    from ov.invoice_returns import annotate_ov_returns

    paid_tokens = [t for t in (config["payment_status_paid_token"], config["payment_status_piggy_token"]) if t]
    paid_payments = Payment.objects.filter(invoice=OuterRef("pk"), is_active=True, status__token__in=paid_tokens)
    money = DecimalField(max_digits=12, decimal_places=2)
    queryset = (
        Invoice.objects.filter(id__in=invoice_ids)
        .select_related("status", "contract")
        .prefetch_related(Prefetch("line_items", queryset=InvoiceLineItem.objects.filter(is_active=True)))
        .annotate(
            webhook_paid=Coalesce(
                Subquery(
                    paid_payments.order_by().values("invoice").annotate(total=Sum("amount")).values("total")[:1],
                    output_field=money,
                ),
                Value(0, output_field=money),
            ),
            webhook_payment_date=Subquery(
                paid_payments.order_by().values("invoice").annotate(last=Max("payment_date")).values("last")[:1]
            ),
        )
        .order_by("id")
    )
    return annotate_ov_returns(queryset, config["payment_status_returned_token"])


def invoice_status_data(invoice, event_type, previous_status, direct_debit_token):
    from billing.utils.invoice_service import get_totals
    from ov.invoice_returns import ov_return_info

    from .events import _amount, _contract_ref, _date, _token_name

    _subtotal, _taxes, _taxes_base, total = get_totals(invoice, line_items=list(invoice.line_items.all()))
    # get_totals pot tornar float: tot a Decimal per restar-hi el pagat
    total = Decimal(str(total or 0))
    paid = Decimal(str(invoice.webhook_paid or 0))
    pending = max(total - paid, Decimal("0"))
    holder_id = invoice.person_id or (invoice.contract.holder_id if invoice.contract else None)
    return_data = None
    if event_type == INVOICE_RETURNED:
        _is_returned, last_return = ov_return_info(invoice)
        if last_return:
            return_data = {"date": _date(last_return["date"]), "reason": last_return["reason"]}
    return {
        "id": invoice.id,
        "token": invoice.token,
        "number": invoice.serie_final,
        "serie": invoice.serie_token_final,
        "issue_date": _date(invoice.issue_date),
        "due_date": _date(invoice.due_date),
        "contract": _contract_ref(invoice.contract),
        "holder": {"id": holder_id} if holder_id else None,
        "previous_status": _token_name(previous_status),
        "status": _token_name(invoice.status),
        "direct_debit": bool(direct_debit_token) and invoice.payment_type_token_final == direct_debit_token,
        "amounts": {"total": _amount(total), "paid": _amount(paid), "pending": _amount(pending), "currency": "EUR"},
        "payment_date": _date(invoice.webhook_payment_date) if event_type == INVOICE_PAID else None,
        "return": return_data,
    }


def _emit_chunks(event_type, rows, config, statuses):
    size = max(1, settings.WEBHOOKS_BILLING_CHUNK_SIZE)
    parts = (len(rows) + size - 1) // size
    done, events = [], 0
    for index in range(parts):
        chunk = rows[index * size:(index + 1) * size]
        previous = {row["invoice_id"]: row["previous_status_id"] for row in chunk}
        try:
            with transaction.atomic():
                invoices = list(_invoices_queryset(list(previous), config))
                data = {
                    "part": index + 1,
                    "parts": parts,
                    "invoices": [
                        invoice_status_data(
                            invoice, event_type, statuses.get(previous[invoice.id]), config["direct_debit_token"]
                        )
                        for invoice in invoices
                    ],
                }
        except Exception:
            logger.exception("No s'han pogut construir les dades d'un avís d'estat de factura")
            continue
        first, last = chunk[0]["invoice_id"], chunk[-1]["invoice_id"]
        event = emit(event_type, "invoices", f"{first}-{last}", lambda data=data: data, schedule=False)
        if event is not None:
            done.extend(chunk)
            events += 1
    return done, events


def scan():
    from billing.models import InvoiceStatus

    if not webhooks_enabled():
        return {"status": "skipped"}

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [SCAN_LOCK_KEY])
            if not cursor.fetchone()[0]:
                return {"status": "busy"}

        config = _config()
        if not WebhookInvoiceState.objects.exists():
            return {"status": "seeded", "invoices": seed_state(config["payment_status_returned_token"])}

        rows = _changed_rows(config, settings.WEBHOOKS_INVOICE_SCAN_LIMIT)
        if not rows:
            return {"status": "success", "changes": 0, "events": 0}

        status_ids = _status_ids(config)
        by_type = {}
        for row in rows:
            event_type = classify(row, status_ids)
            if event_type:
                by_type.setdefault(event_type, []).append(row)

        notifiable = _notifiable_ids(
            [row["invoice_id"] for type_rows in by_type.values() for row in type_rows],
            config["invoice_type_budget_token"],
        )
        statuses = {status.id: status for status in InvoiceStatus.objects.all()}
        failed, events = set(), 0
        for event_type, type_rows in by_type.items():
            type_rows = [row for row in type_rows if row["invoice_id"] in notifiable]
            if not type_rows:
                continue
            done, created = _emit_chunks(event_type, type_rows, config, statuses)
            events += created
            done_ids = {row["invoice_id"] for row in done}
            failed.update(row["invoice_id"] for row in type_rows if row["invoice_id"] not in done_ids)

        WebhookInvoiceState.objects.bulk_create(
            [
                WebhookInvoiceState(invoice_id=row["invoice_id"], status_id=row["status_id"], is_returned=row["is_returned"])
                for row in rows
                if row["invoice_id"] not in failed
            ],
            update_conflicts=True,
            unique_fields=["invoice_id"],
            update_fields=["status_id", "is_returned", "updated_at"],
            batch_size=1000,
        )

        if events and webhooks_configured():
            transaction.on_commit(dispatcher.schedule_send)

    if failed:
        logger.warning("Avisos d'estat de factura: %s factures es tornaran a provar", len(failed))
    return {"status": "success", "changes": len(rows), "events": events, "retry": len(failed)}
