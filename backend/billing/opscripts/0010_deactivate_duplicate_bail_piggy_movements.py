"""Second pass: deactivate leftover duplicate bail-return piggy movements.

0009 required payment.status == piggy AND movement.current_status == piggy AND
invoice__bail. Some payments (e.g. id 66345) were missed when Bail.invoice was
not linked or when payment.status / movement.current_status diverged after the
liquidation.

Keep active BALANCE movements; soft-deactivate other active siblings that share
the same current_status as that BALANCE movement.
"""
from django.core.management.color import color_style
from django.db.models import Q

from billing.models import Payment, PaymentMovement
from coredata.models import ConfigProject

style = color_style()


def run():
    try:
        piggy_token = ConfigProject.objects.get(token='payment_status_piggy_token').value
    except ConfigProject.DoesNotExist:
        return

    bail_invoice_q = (
        Q(invoice__bail__isnull=False)
        | Q(invoice__title_final__icontains='RETORN FIANÇA')
        | Q(name__icontains='RETORN FIANÇA')
    )
    piggy_q = Q(status__token=piggy_token) | Q(movements__current_status__token=piggy_token)

    payments = (
        Payment.objects.filter(is_active=True)
        .filter(bail_invoice_q)
        .filter(piggy_q)
        .distinct()
        .prefetch_related('movements', 'movements__payment_type', 'movements__current_status')
    )

    to_deactivate_ids = []
    payments_fixed = 0
    for payment in payments:
        active = [m for m in payment.movements.all() if m.is_active]
        balance = [
            m for m in active
            if m.payment_type_id and m.payment_type.token == 'BALANCE'
        ]
        if not balance:
            continue

        # Prefer BALANCE movements whose current_status is piggy; if none match
        # (status ids diverged) but the payment itself is piggy, use all BALANCE.
        piggy_balance = [
            m for m in balance
            if m.current_status_id and m.current_status.token == piggy_token
        ]
        payment_is_piggy = bool(payment.status_id and payment.status.token == piggy_token)
        target_balance = piggy_balance or (balance if payment_is_piggy else [])
        if not target_balance:
            continue

        status_ids = {m.current_status_id for m in target_balance if m.current_status_id}
        duplicates = [
            m for m in active
            if m.current_status_id in status_ids
            and not (m.payment_type_id and m.payment_type.token == 'BALANCE')
        ]
        if not duplicates:
            continue

        to_deactivate_ids.extend(m.id for m in duplicates)
        payments_fixed += 1

    if to_deactivate_ids:
        updated = PaymentMovement.objects.filter(id__in=to_deactivate_ids).update(is_active=False)
        print(style.SUCCESS(
            f"Deactivated {updated} non-BALANCE piggy movements "
            f"across {payments_fixed} bail-return payments"
        ))
    else:
        print(style.SUCCESS("No duplicate bail piggy movements to deactivate"))
