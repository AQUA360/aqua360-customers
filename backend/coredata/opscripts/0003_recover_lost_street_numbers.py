"""Recupera els números de carrer que s'han perdut en actualitzar l'adreça d'un comptador.

En alguns casos, en desar l'adreça d'un comptador el `StreetNumber` quedava amb el tipus
N/R/S però amb `number` i `number_suffix` buits, de manera que es mostra en blanc (com si
fos S/N). Aquest script els detecta i els omple amb el número dels punts de subministrament
relacionats (`SupplyPoint.address.street_number`), que és l'adreça de referència:

- Comptador, escomesa i finca: els seus punts de subministrament.
- Bateria (i escomesa, a través de les seves bateries): els punts de les seves boques.
- Posició de ruta: els punts de les seves finques.

Només es recupera quan totes les fonts coincideixen en un únic número (no S/N) i el carrer
de la font és el mateix que el del `StreetNumber`. Com que hi ha carrers duplicats amb
grafies diferents (abreviatura, majúscules, accents, errates), es considera el mateix
carrer si els noms normalitzats són prou semblants i no són de poblacions diferents.
La resta de casos (sense fonts, fonts discrepants o carrer diferent) es llisten per
revisar-los a mà.
"""
import unicodedata
from difflib import SequenceMatcher

from django.db.models import Q

from coredata.models import StreetNumber
from service.models import Cluster, Connection, Meter, Property, RoutePosition, SupplyPoint

NUMBER_FIELDS = ('number', 'number_end', 'number_suffix', 'number_end_suffix')
STREET_NAME_MIN_SIMILARITY = 0.8


def _lost_street_numbers():
    return (
        StreetNumber.objects
        .filter(number__isnull=True)
        .filter(Q(number_suffix__isnull=True) | Q(number_suffix=''))
        .filter(Q(number_end__isnull=True))
        .filter(Q(number_end_suffix__isnull=True) | Q(number_end_suffix=''))
        .exclude(number_type__isnull=True)
        .exclude(number_type__type='SN')
        .select_related('street', 'number_type')
    )


def _related_supply_points(street_number):
    """Punts de subministrament de les entitats que fan servir aquest StreetNumber."""
    connections = Connection.objects.filter(address_street_number=street_number)
    return SupplyPoint.objects.filter(
        Q(meter__in=Meter.objects.filter(address_street_number=street_number))
        | Q(connection__in=connections)
        | Q(cluster_nozzle__cluster__connection__in=connections)
        | Q(property__in=Property.objects.filter(address_street_number=street_number))
        | Q(cluster_nozzle__cluster__in=Cluster.objects.filter(address_street_number=street_number))
        | Q(property__route_position__in=RoutePosition.objects.filter(address_street_number=street_number))
    ).select_related('address__street_number__street', 'address__street_number__number_type').distinct()


def _normalize(name):
    name = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode()
    return ''.join(char for char in name.upper() if char.isalnum())


def _same_street(street, other):
    if street is None or other is None:
        return street is other
    if street.id == other.id:
        return True
    if street.city_id and other.city_id and street.city_id != other.city_id:
        return False
    similarity = SequenceMatcher(None, _normalize(street.name), _normalize(other.name)).ratio()
    return similarity >= STREET_NAME_MIN_SIMILARITY


def _value(street_number):
    return (street_number.number_type_id,) + tuple(
        getattr(street_number, field) or None for field in NUMBER_FIELDS
    )


def _candidates(street_number):
    """Valors (tipus + camps de número) de les fonts vàlides, i si n'hi ha d'un altre carrer."""
    values = {}
    other_street = False
    for supply_point in _related_supply_points(street_number):
        source = supply_point.address.street_number if supply_point.address else None
        if source is None or source.id == street_number.id:
            continue
        if source.number_type is None or source.number_type.type == 'SN' or not str(source).strip():
            continue
        if not _same_street(street_number.street, source.street):
            other_street = True
            continue
        values.setdefault(_value(source), source)
    return values, other_street


def run():
    recovered, conflicts, other_street, no_source = [], [], [], []

    for street_number in _lost_street_numbers().iterator(chunk_size=500):
        values, has_other_street = _candidates(street_number)
        if len(values) == 1:
            source = next(iter(values.values()))
            street_number.number_type_id = source.number_type_id
            for field in NUMBER_FIELDS:
                setattr(street_number, field, getattr(source, field))
            street_number.save(update_fields=('number_type', *NUMBER_FIELDS, 'updated_at'))
            recovered.append(street_number.id)
        elif len(values) > 1:
            conflicts.append(street_number.id)
        elif has_other_street:
            other_street.append(street_number.id)
        else:
            no_source.append(street_number.id)

    print(f"StreetNumber recuperats: {len(recovered)}")
    print(f"Per revisar, fonts amb números diferents: {len(conflicts)} {conflicts}")
    print(f"Per revisar, fonts d'un altre carrer: {len(other_street)} {other_street}")
    print(f"Sense font per recuperar-los: {len(no_source)} {no_source}")
