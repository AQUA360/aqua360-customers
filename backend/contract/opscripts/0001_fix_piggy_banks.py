from django.core.management.color import color_style
from decimal import Decimal
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce
from contract.models import PiggyBank

style = color_style()


def run():
    try:
        print("Fixing piggy banks...")
        amount_field = DecimalField(max_digits=10, decimal_places=2)
        piggy_banks = PiggyBank.objects.annotate(
                total_amount=Coalesce(
                Sum(
                    Case(
                        When(movements__is_positive=True, then=F('movements__amount')),
                        When(movements__is_positive=False, then=-F('movements__amount')),
                        default=Value(Decimal('0.00')),
                        output_field=amount_field,
                    )
                ),
                Value(Decimal('0.00')),
                output_field=amount_field,
            )
        ).exclude(
            amount=F('total_amount')
        )
        print(f"Found {piggy_banks.count()} piggy banks to update")
        to_update = []
        for pb in piggy_banks:
            pb.amount = pb.total_amount if pb.total_amount >= 0 else  0
            to_update.append(pb)

        PiggyBank.objects.bulk_update(to_update, ['amount'])
    except Exception as e:
        print(f"Error fixing piggy banks: {e}")
