import datetime
from django.core.management.color import color_style
from django.db.models import F

from billing.models import PaymentMovement, PaymentRemittanceReturn

style = color_style()

def run(dry_run=False):
    movements = PaymentMovement.objects.filter(
            timestamp__gte=datetime.datetime(2026, 7, 1),
            is_positive=False,
            payment_type__token="DIRECT_DEBIT",
            payment__remittances_returns__isnull=False,
        )
    failed_movements = []
    print(style.SUCCESS(f"\nUpdating {len(movements)} movements ROUND TWO❗"))
    for movement in movements:
        payment = movement.payment
        remittance_return = payment.remittances_returns.filter(return_date__gte=movement.movement_date).order_by("return_date").first()
        if remittance_return:
            try:
                movement.movement_date = remittance_return.return_date
                movement.save()
            except Exception as e:
                failed_movements.append(movement.id)
    try:
        payment_remittances = PaymentRemittanceReturn.objects.all()
        payment_remittances.update(created_at=F("return_date"))
    except Exception as e:
        print(style.ERROR(f"Failed to update payment remittances created at: {e}"))
    if failed_movements:
        print(style.ERROR(f"Failed to update {len(failed_movements)} movements"))
        print(style.ERROR(f"Failed movement ids: {failed_movements}"))
    print(style.SUCCESS(f"\nUpdated {len(movements) - len(failed_movements)} movements"))

