"""Omple el número de carrer de les escomeses que només tenen el nom del carrer.

Moltes escomeses importades tenen un `StreetNumber` sense número ni tipus. El 0003 ja en
recupera la majoria a partir dels punts de subministrament relacionats; aquest script resol
la resta agafant l'adreça de referència segons el tipus d'instal·lació de l'escomesa:

- Bateria: l'adreça de les seves bateries (`Cluster`). Si no en té cap, la dels seus punts.
- Individual (o sense tipus): l'adreça dels seus punts de subministrament.

L'escomesa passa a apuntar al carrer i número de la font (no es modifica el `StreetNumber`,
que pot ser compartit). Només es fa quan totes les fonts coincideixen en un únic número; les
escomeses marcades explícitament com a S/N no es toquen. Les que canvien de carrer i les que
no es poden resoldre es llisten per revisar-les.
"""
import unicodedata

from django.db.models import Q

from service.models import Connection

NUMBER_FIELDS = ('number', 'number_end', 'number_suffix', 'number_end_suffix')


def _connections_without_number():
    return (
        Connection.objects
        .filter(is_active=True)
        .filter(Q(address_street_number__isnull=True) | (
            Q(address_street_number__number__isnull=True)
            & Q(address_street_number__number_end__isnull=True)
            & (Q(address_street_number__number_suffix__isnull=True) | Q(address_street_number__number_suffix=''))
        ))
        .exclude(address_street_number__number_type__type='SN')
        .select_related('address_street', 'installation_type')
    )


def _sources(connection):
    """(carrer, número) de l'adreça de referència de l'escomesa."""
    if connection.installation_type and connection.installation_type.token == 'cluster':
        clusters = connection.clusters.filter(is_active=True).select_related(
            'address_street', 'address_street_number__number_type'
        )
        if clusters:
            return [(cluster.address_street, cluster.address_street_number) for cluster in clusters]
    supply_points = connection.supply_points.filter(is_active=True, address__isnull=False).select_related(
        'address__street', 'address__street_number__number_type'
    )
    return [(sp.address.street, sp.address.street_number) for sp in supply_points]


def _has_number(street_number):
    return (
        street_number is not None
        and street_number.number_type is not None
        and street_number.number_type.type not in ('SN', '')
        and str(street_number).strip() != ''
    )


def _normalize(name):
    name = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode()
    return ''.join(char for char in name.upper() if char.isalnum())


def _key(street, street_number):
    return (_normalize(street.name if street else ''), street_number.number_type_id) + tuple(
        getattr(street_number, field) or None for field in NUMBER_FIELDS
    )


def run():
    filled, other_street, conflicts, no_number, no_source = [], [], [], [], []

    for connection in _connections_without_number().iterator(chunk_size=500):
        sources = _sources(connection)
        if not sources:
            no_source.append(connection.id)
            continue

        values = {}
        for street, street_number in sources:
            if street is not None and _has_number(street_number):
                values.setdefault(_key(street, street_number), (street, street_number))
        if not values:
            no_number.append(connection.id)
            continue
        if len(values) > 1:
            conflicts.append(connection.id)
            continue

        street, street_number = next(iter(values.values()))
        current_street = connection.address_street
        if current_street is None or _normalize(current_street.name) != _normalize(street.name):
            other_street.append(connection.id)
        connection.address_street = street
        connection.address_street_number = street_number
        connection.save(update_fields=('address_street', 'address_street_number', 'updated_at'))
        filled.append(connection.id)

    print(f"Escomeses amb el número omplert: {len(filled)}")
    print(f"  d'aquestes, amb canvi de carrer (per revisar): {len(other_street)} {other_street}")
    print(f"Per revisar, fonts amb números diferents: {len(conflicts)} {conflicts}")
    print(f"Sense número a la font (S/N): {len(no_number)}")
    print(f"Sense font: {len(no_source)} {no_source}")
