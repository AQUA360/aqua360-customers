from django.utils.translation import gettext as _

from coredata.models import ConfigProject
from pricing.utils.return_fee_service import RETURN_FEE_CONFIG_TOKENS

# ConfigProject que apunten a una tarifa pel seu token: si s'eliminés, el procés que la fa servir
# deixaria de funcionar sense avisar
PRICE_RATE_CONFIG_TOKENS = [*RETURN_FEE_CONFIG_TOKENS, 'connection_rights_price_rate_token']


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
        # Hi ha línies de factura que només porten el concepte, sense la tarifa directa
        or InvoiceLineItem.objects.filter(line_item_type__billing_range__price_rate__in=price_rate_ids).exists()
    )


def price_rate_configured(price_rates):
    """Indica si alguna de les tarifes és la que indica un ConfigProject (despeses de devolució, drets de connexió)."""
    tokens = [price_rate.token for price_rate in price_rates if price_rate.token]
    return bool(tokens) and ConfigProject.objects.filter(token__in=PRICE_RATE_CONFIG_TOKENS, value__in=tokens).exists()


def price_rate_deletion_error(price_rate):
    """Motiu pel qual no es pot eliminar la tarifa, o None si es pot eliminar."""
    if price_rate_in_use([price_rate.id]):
        return _("No es pot eliminar la tarifa perquè està vinculada a contractes o factures.")
    if price_rate_configured([price_rate]):
        return _("No es pot eliminar la tarifa perquè està configurada com a despeses de devolució o drets de connexió.")
    return None


def product_deletion_error(product):
    """Motiu pel qual no es pot eliminar el producte, o None si es pot eliminar."""
    from billing.models import InvoiceLineItem
    from contract.models import Bail

    price_rates = list(product.price_rates.all())
    if (
        InvoiceLineItem.objects.filter(product=product).exists()
        or Bail.objects.filter(product=product).exists()
        or (price_rates and price_rate_in_use([price_rate.id for price_rate in price_rates]))
    ):
        return _("No es pot eliminar el producte perquè està vinculat a contractes o factures.")
    if price_rate_configured(price_rates):
        return _("No es pot eliminar el producte perquè una de les seves tarifes està configurada com a despeses de devolució o drets de connexió.")
    return None
