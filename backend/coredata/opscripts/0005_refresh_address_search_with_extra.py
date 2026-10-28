"""Recalcula `Address.address_search` de les adreces amb ampliació.

`address_search` es desa a partir de `str(Address)` a cada `save()`. Ara que
l'ampliació forma part de l'adreça completa, les adreces que ja la tenien
informada no la mostren al cercador fins que es tornin a desar. Es fa amb
`update()` per no tocar `updated_at`.
"""
from coredata.models import Address


def run():
    addresses = (
        Address.objects.exclude(address_extra__isnull=True)
        .exclude(address_extra='')
        .select_related('street__type', 'street_number__number_type', 'city', 'country')
    )
    max_length = Address._meta.get_field('address_search').max_length
    for address in addresses.iterator():
        address_search = str(address).strip()[:max_length]
        if address.address_search != address_search:
            Address.objects.filter(id=address.id).update(address_search=address_search)
