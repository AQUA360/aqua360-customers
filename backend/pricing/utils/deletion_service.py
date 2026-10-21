def price_rate_in_use(price_rate_ids):
    """Indica si alguna de les tarifes està vinculada a un contracte, una sol·licitud o una factura."""
    # Imports locals: contract i billing ja importen models de pricing
    from billing.models import InvoiceLineItem
    from contract.models import Bail, Contract, ContractPriceRate, ContractPriceRateHistory, ContractRequest

    return (
        ContractPriceRate.objects.filter(price_rate__in=price_rate_ids).exists()
        or ContractPriceRateHistory.objects.filter(price_rate__in=price_rate_ids).exists()
        or Contract.objects.filter(registration_price_rates__in=price_rate_ids).exists()
        or ContractRequest.objects.filter(registration_price_rates__in=price_rate_ids).exists()
        or Bail.objects.filter(price_rate__in=price_rate_ids).exists()
        or InvoiceLineItem.objects.filter(price_rate__in=price_rate_ids).exists()
    )


def product_in_use(product):
    """Indica si el producte, o alguna de les seves tarifes, està vinculat a un contracte o una factura."""
    from billing.models import InvoiceLineItem
    from contract.models import Bail

    if InvoiceLineItem.objects.filter(product=product).exists():
        return True
    if Bail.objects.filter(product=product).exists():
        return True
    price_rate_ids = list(product.price_rates.values_list('id', flat=True))
    return bool(price_rate_ids) and price_rate_in_use(price_rate_ids)
