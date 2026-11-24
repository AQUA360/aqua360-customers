"""Retorn bancari dels rebuts d'una factura, per a l'OV.

Quan el banc retorna un rebut domiciliat, qui queda en estat retornat és el
rebut (`Payment`); la factura torna a Confirmada o Vençuda i no té cap estat
«retornada». Aquí es calcula, a partir dels rebuts actius de la factura:

- `is_returned`: algun rebut actiu continua en estat retornat
  (`payment_status_returned_token`), el mateix criteri que fa servir
  `POST /ov/invoice/return-request/` per respondre `409`.
- `last_return`: data i motiu del darrer retorn, encara que després s'hagi
  tornat a cobrar. Surt dels moviments de retorn dels rebuts; si un rebut
  retornat no en té (dades antigues), de la data i el motiu del rebut.

Els valors s'afegeixen com a anotacions a la consulta de factures
(`annotate_ov_returns`), per no fer consultes per factura als llistats.
"""

from django.db.models import BooleanField, Exists, F, OuterRef, Subquery, Value
from django.db.models.fields import CharField, DateField

from billing.models import Invoice, Payment, PaymentMovement
from coredata.models import ConfigProject

RETURN_ANNOTATIONS = (
    "ov_is_returned",
    "ov_has_return_movement",
    "ov_return_movement_date",
    "ov_return_movement_code",
    "ov_return_movement_name",
    "ov_return_payment_date",
    "ov_return_payment_code",
    "ov_return_payment_name",
)


def returned_payment_status_token():
    return (
        ConfigProject.objects.filter(token="payment_status_returned_token")
        .values_list("value", flat=True)
        .first()
    )


def annotate_ov_returns(queryset, returned_token=None):
    """Afegeix a la consulta de factures les anotacions de `RETURN_ANNOTATIONS`.
    Sense el token de rebut retornat configurat, cap factura consta retornada."""
    if returned_token is None:
        returned_token = returned_payment_status_token()
    if not returned_token:
        return queryset.annotate(
            ov_is_returned=Value(False, output_field=BooleanField()),
            ov_has_return_movement=Value(False, output_field=BooleanField()),
            **{
                name: Value(None, output_field=CharField())
                for name in RETURN_ANNOTATIONS[2:]
            },
        )

    returned_payments = Payment.objects.filter(
        invoice=OuterRef("pk"), is_active=True, status__token=returned_token
    )
    # Els moviments sense data, al final: PostgreSQL posa els NULL primer en
    # ordre descendent
    return_movements = PaymentMovement.objects.filter(
        payment__invoice=OuterRef("pk"),
        payment__is_active=True,
        is_active=True,
        current_status__token=returned_token,
    ).order_by(F("movement_date").desc(nulls_last=True), "-timestamp", "-id")
    # Rebuts retornats sense cap moviment de retorn (dades antigues): la data i
    # el motiu són al mateix rebut
    returned_without_movements = (
        returned_payments.exclude(
            Exists(
                PaymentMovement.objects.filter(
                    payment=OuterRef("pk"),
                    is_active=True,
                    current_status__token=returned_token,
                )
            )
        )
        .exclude(reject_date__isnull=True, reject__isnull=True)
        .order_by(F("reject_date").desc(nulls_last=True), "-id")
    )

    return queryset.annotate(
        ov_is_returned=Exists(returned_payments),
        ov_has_return_movement=Exists(return_movements),
        ov_return_movement_date=Subquery(
            return_movements.values("movement_date")[:1], output_field=DateField()
        ),
        ov_return_movement_code=Subquery(
            return_movements.values("reject_motive__token")[:1]
        ),
        ov_return_movement_name=Subquery(
            return_movements.values("reject_motive__name")[:1]
        ),
        ov_return_payment_date=Subquery(
            returned_without_movements.values("reject_date")[:1],
            output_field=DateField(),
        ),
        ov_return_payment_code=Subquery(
            returned_without_movements.values("reject__token")[:1]
        ),
        ov_return_payment_name=Subquery(
            returned_without_movements.values("reject__name")[:1]
        ),
    )


def _reason(code, name):
    if not code and not name:
        return None
    return {"code": code, "name": name}


def ov_return_info(invoice):
    """`(is_returned, last_return)` d'una factura anotada amb
    `annotate_ov_returns`. Si no ho està (p. ex. una factura que arriba d'una
    altra consulta), la torna a llegir anotada: una consulta més."""
    if not hasattr(invoice, "ov_is_returned"):
        annotated = (
            annotate_ov_returns(Invoice.objects.filter(pk=invoice.pk))
            .values(*RETURN_ANNOTATIONS)
            .first()
        ) or {}
        for name in RETURN_ANNOTATIONS:
            setattr(invoice, name, annotated.get(name))

    last_return = None
    movement_date = invoice.ov_return_movement_date
    payment_date = invoice.ov_return_payment_date
    # El darrer retorn conegut: el moviment de retorn més recent (encara que no
    # tingui data) o, si un rebut retornat sense moviments té una data
    # posterior (o el moviment no en té), el d'aquest rebut
    payment_is_newer = payment_date is not None and (
        movement_date is None or payment_date > movement_date
    )
    if invoice.ov_has_return_movement and not payment_is_newer:
        last_return = {
            "date": movement_date,
            "reason": _reason(
                invoice.ov_return_movement_code, invoice.ov_return_movement_name
            ),
        }
    elif payment_date or invoice.ov_return_payment_code or invoice.ov_return_payment_name:
        last_return = {
            "date": payment_date,
            "reason": _reason(
                invoice.ov_return_payment_code, invoice.ov_return_payment_name
            ),
        }
    return bool(invoice.ov_is_returned), last_return
