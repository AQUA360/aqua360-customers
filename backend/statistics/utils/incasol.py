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
