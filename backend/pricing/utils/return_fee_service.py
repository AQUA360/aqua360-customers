"""Vinculació automàtica de la tarifa de despeses de devolució.

Les despeses de devolució (`invoice_return_charge()`) no es reconeixen per cap
origen ni tipus de factura propi: es reconeixen perquè la factura té una línia
amb una `PriceRate` concreta, i aquesta `PriceRate` s'identifica pel token
guardat als `ConfigProject` de `RETURN_FEE_CONFIG_TOKENS`.

Fins ara aquests `ConfigProject` s'havien de posar a mà (SQL o admin) cada cop
que un client estrenava la tarifa. Amb `PriceRate.is_return_fee` n'hi ha prou
de marcar la casella al formulari de tarifes: aquest mòdul manté els
`ConfigProject` sincronitzats amb el token de la tarifa marcada.
"""

from coredata.models import ConfigProject


# Tots els ConfigProject que han d'apuntar al token de la tarifa de despeses de
# devolució. Si algun dia n'apareix un altre, afegir-lo aquí és tot el que cal
# perquè es vinculi sol.
RETURN_FEE_CONFIG_TOKENS = {
    'invoice_return_price_rate_token': "Token Price Rate Invoice Return",
    'claim_letter_return_fee_price_rate_token': (
        "Token de la tarifa (PriceRate) de despeses de devolució a la carta de suspensió"
    ),
}


def sync_return_fee_config(price_rate):
    """Deixa els `ConfigProject` coherents amb `price_rate.is_return_fee`.

    Si la tarifa és la de despeses de devolució, desmarca qualsevol altra (només
    n'hi pot haver una) i escriu el seu token a tots els `ConfigProject`,
    creant-los si encara no existeixen. Si s'ha desmarcat, buida només els
    `ConfigProject` que apuntaven a aquesta tarifa; els que ja apuntessin a una
    altra no es toquen.

    Retorna el token que ha quedat configurat, o `None` si s'ha buidat.
    """
    from ..models import PriceRate

    if price_rate.is_return_fee:
        if not price_rate.token:
            # Sense token no hi ha res a configurar: els ConfigProject guarden
            # el token de la tarifa, no el seu id.
            return None
        PriceRate.objects.filter(is_return_fee=True).exclude(pk=price_rate.pk).update(is_return_fee=False)
        value = price_rate.token
    else:
        value = None

    for token, name in RETURN_FEE_CONFIG_TOKENS.items():
        if value is None:
            # Només es buida el que apuntava a aquesta tarifa.
            configs = ConfigProject.objects.filter(token=token, value=price_rate.token)
        else:
            ConfigProject.objects.get_or_create(
                token=token,
                defaults={'name': name, 'value': value},
            )
            configs = ConfigProject.objects.filter(token=token)
        for config in configs:
            if config.value != value:
                config.value = value
                config.save(update_fields=['value', 'updated_at'])

    return value
