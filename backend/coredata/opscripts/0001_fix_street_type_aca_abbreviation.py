"""Omple `StreetType.aca_abbreviation` per als tipus de via que encara no en
tenen, seguint la llista de valors "5.2 Tipus de via" del document de l'ACA
"04_estructura_fitxer_registre_ampliacio.pdf".

Substitueix les migracions de dades 0125/0126 (unificades aquí): com que
`abbreviation` és el camp que en la pràctica sempre està informat (`name` sol
estar buit als entorns reals), el mapeig es fa per `abbreviation`. Els casos
directes (AV, PL, CR...) es resolen per equivalència directa; els casos
ambigus (BA, CL, CN, DR, ST, STA...) es van desxifrar mirant els noms reals
dels carrers que fan servir cada tipus (p.ex. 'DR ...' -> "Carrer
del Doctor ..." -> Carrer; 'BA ...' -> "Baixada ...").

Els `abbreviation` amb massa poca evidència (CAP, R, PRES, P, TTE, MTROS,
PAS) es deixen deliberadament sense tocar: és preferible que l'exportació
ACA apliqui el valor per defecte "VP" (Via Pública Indeterminada) abans que
inventar un codi (veure `contract/utils/aca_bonification_export_service.py`
`_street_type_code`).
"""
from coredata.models import StreetType

ACA_ABBREVIATION_BY_ABBREVIATION = {
    'AV': 'AV', 'AVDA': 'AV', 'AVD': 'AV', 'AVGDA': 'AV',
    'PL': 'PL', 'PZ': 'PL', 'PÇA': 'PL', 'PLZ': 'PL', 'PÇ': 'PL', 'PZA': 'PL', 'Plz': 'PL',
    'PS': 'PG', 'PG': 'PG', 'PY': 'PG',
    'CR': 'CR', 'C': 'CR', 'CALLE': 'CR', 'C/': 'CR', 'CL': 'CR', 'DR': 'CR', 'ST': 'CR', 'STA': 'CR',
    'PA': 'PA',
    'TO': 'TO', 'TT': 'TO',
    'PJ': 'PT', 'PJE': 'PT', 'PGE': 'PT', 'PTG': 'PT', 'PAS': 'PT',
    'UR': 'UB', 'URB': 'UB',
    'CT': 'CA', 'CTRA': 'CA',
    'RR': 'RR',
    'POL': 'PO',
    'RDA': 'RD', 'RD': 'RD',
    'RBLA': 'RB', 'RB': 'RB',
    'CM': 'CM',
    'APTDO': 'AP', 'AP': 'AP',
    'BO': 'BO', 'B': 'BO',
    'RU': 'RU',
    'VIA': 'VI',
    'BA': 'BD',
    'CN': 'CL',
    'TRAV': 'TR',
    'J': 'JR',
    'G': 'GP',
    'M': 'MS',
    'RA': 'AR',
}


def run():
    for abbreviation, aca_abbreviation in ACA_ABBREVIATION_BY_ABBREVIATION.items():
        StreetType.objects.filter(
            abbreviation=abbreviation, aca_abbreviation__isnull=True
        ).update(aca_abbreviation=aca_abbreviation)
