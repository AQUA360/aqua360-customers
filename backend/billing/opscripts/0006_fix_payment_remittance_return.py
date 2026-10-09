import datetime
from django.core.management.color import color_style
from django.db.models import F

from billing.models import PaymentMovement, PaymentRemittanceReturn

style = color_style()

def run(dry_run=False):
    return_remittances = PaymentRemittanceReturn.objects.all()
    try:
        for return_remittance in return_remittances:
            payments = return_remittance.payments.filter(
                is_active=True,
            )
            movements = PaymentMovement.objects.filter(
                payment__in=payments,
                is_positive=False,
                timestamp__date=return_remittance.created_at.date(),
            )
            movements.update(movement_date=return_remittance.return_date)
    except Exception as e:
        print(style.ERROR(f"Failed to update return remittances movements date: {e}"))

