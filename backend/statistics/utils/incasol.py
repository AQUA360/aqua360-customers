"""Resolució del número de concert INCASOL.

El número és propi de cada explotació (`Exploitation.incasol_num`). Les instal·lacions
que encara no l'han omplert cauen al valor global de sempre (`ConfigProject` amb token
`incasol_num`), de manera que els informes no canvien de comportament fins que algú
informa el camp a la fitxa de l'explotació.

El prefix "S" i la composició del número de liquidació els fa cada informe: aquí només
es retorna el número nu.
"""

from coredata.models import ConfigProject
from service.models import Exploitation


def resolve_incasol_num(exploitation_id=None, default=""):
    if exploitation_id:
        exploitation = Exploitation.objects.filter(id=exploitation_id).first()
        if exploitation and exploitation.incasol_num:
            return exploitation.incasol_num

    config = ConfigProject.objects.filter(token='incasol_num').first()
    return config.value if config and config.value else default


def resolve_municipi(supply_point):
    """Municipi del punt de subministrament per als informes INCASOL.

    Es fa servir la població de l'adreça (o la del carrer). El nom de l'explotació només
    és l'últim recurs: no és una població i l'INCASOL espera el municipi.
    """
    address = supply_point.address if supply_point else None
    if address:
        if address.city and address.city.name:
            return address.city.name.upper()
        if address.city_name:
            return address.city_name.upper()
        if address.street and address.street.city and address.street.city.name:
            return address.street.city.name.upper()

    connection = supply_point.connection if supply_point else None
    exploitation = connection.exploitation if connection else None
    return exploitation.name.upper() if exploitation and exploitation.name else ""
