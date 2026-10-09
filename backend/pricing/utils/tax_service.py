from django.db.models import F, Q
from django.utils import timezone

from pricing.models import Tax


def same_tax_percent(tax, percent):
    if tax is None or getattr(tax, 'percent', None) is None or percent is None:
        return False
    try:
        return abs(float(tax.percent) - float(percent)) < 0.001
    except (TypeError, ValueError):
        return False


def tax_by_percent(percent):
    """Impost amb aquest percentatge.

    El percentatge no és únic: el catàleg nou i la importació antiga poden
    conviure, tots dos actius i sense data de fi. Es queda l'actiu vigent
    amb la data d'inici més recent.
    """
    if percent is None:
        return None
    try:
        percent_value = float(percent)
    except (TypeError, ValueError):
        return None

    candidates = Tax.objects.filter(percent=percent_value)
    active = candidates.filter(is_active=True)
    pool = active if active.exists() else candidates
    if not pool.exists():
        return None

    today = timezone.localdate()
    in_range = pool.filter(
        Q(start__isnull=True) | Q(start__lte=today),
        Q(end__isnull=True) | Q(end__gte=today),
    )
    if in_range.exists():
        pool = in_range
    return pool.order_by(F('start').desc(nulls_last=True), 'position', 'id').first()


def resolve_tax_for_line_item(validated_data):
    """Impost d'una línia de factura.

    Si el client (o el tipus de línia) ja indica un impost i el percentatge
    quadra, es conserva. Només es busca per percentatge quan no n'hi ha cap.
    """
    percent = validated_data.get('tax_percent', None)
    sent_tax = validated_data.get('tax')
    if same_tax_percent(sent_tax, percent):
        return sent_tax

    line_item_type = validated_data.get('line_item_type')
    line_item_tax = getattr(line_item_type, 'tax', None) if line_item_type is not None else None
    if same_tax_percent(line_item_tax, percent):
        return line_item_tax

    return tax_by_percent(percent)
