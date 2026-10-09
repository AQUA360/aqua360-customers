# -*- coding: utf-8 -*-
"""Resolució de tipus de via contra el catàleg de l'ACA.

`coredata_streettype` ha de contenir només els 71 codis oficials de l'ACA. La taula no està
bloquejada: el que la manté neta és que cap camí del codi hi crea files:
o el tipus que arriba d'un import es reconeix i es retorna la fila del catàleg, o no hi ha
tipus (None) i el carrer es guarda sense tipus, que és recuperable, en lloc d'omplir el
catàleg de brossa.
"""
from coredata.aca_street_types import code_from_street_name, code_from_token
from coredata.models import StreetType


def resolve_street_type(abbreviation=None, name=None):
    """Retorna la `StreetType` del catàleg ACA que correspon a l'abreviació/nom rebuts.

    Prova, en aquest ordre: l'abreviació (codi ACA o grafia històrica coneguda), el nom del
    tipus, i el prefix del nom si el que ha arribat és el nom sencer d'un carrer. Retorna
    None si no es reconeix res: NO crea cap fila.
    """
    code = code_from_token(abbreviation) or code_from_token(name)
    if not code and name:
        code, _rest = code_from_street_name(name)
    if not code:
        return None
    return StreetType.objects.filter(aca_abbreviation=code).first()
