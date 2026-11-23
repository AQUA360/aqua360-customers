"""Deactivate duplicate PaymentMovements on bail-return payments in piggy status.

Before disconnect_payment_signals was added in liquidate_bail, saving the payment
to payment_status_piggy created a second movement via the payment signal (with the
invoice payment type, e.g. BANK_TRANSFER) in addition to the explicit BALANCE
movement. Accounting treats both active piggy movements, so the amount was doubled.

Keep the BALANCE movement; soft-deactivate the rest (is_active=False).
"""
from django.core.management.color import color_style

from billing.models import Payment, PaymentMovement
from coredata.models import ConfigProject

style = color_style()


def run():
    try:
        piggy_token = ConfigProject.objects.get(token='payment_status_piggy_token').value
    except ConfigProject.DoesNotExist:
        return

    payments = (
        Payment.objects.filter(
            status__token=piggy_token,
            invoice__bail__isnull=False,
            is_active=True,
        )
        .distinct()
        .prefetch_related('movements', 'movements__payment_type', 'movements__current_status')
    )

    to_deactivate_ids = []
    payments_fixed = 0
    for payment in payments:
        piggy_movements = [
            m for m in payment.movements.all()
            if m.is_active and m.current_status_id and m.current_status.token == piggy_token
        ]
        if len(piggy_movements) < 2:
            continue

        balance = [m for m in piggy_movements if m.payment_type_id and m.payment_type.token == 'BALANCE']
        duplicates = [m for m in piggy_movements if not (m.payment_type_id and m.payment_type.token == 'BALANCE')]
        if not balance or not duplicates:
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
