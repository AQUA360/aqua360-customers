from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def round_ceil(value, to_int=False, round_zero=False):
    """Round value to 2 decimal places. Treats None and non-numeric values as 0."""
    if value is None:
        return 0.0
    try:
        if to_int:
            if round_zero and (Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) > 0) and int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) == 0:
                return 1
            return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        else:
            return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0