"""
Protecció contra la injecció de fórmules als CSV que es descarreguen per obrir amb Excel.

En un CSV no es pot indicar el tipus de cel·la: Excel interpreta com a fórmula
qualsevol text que comenci per `=`, `+`, `-` o `@` (o per tabulador o retorn).
Si aquest text ve de dades que escriuen els usuaris, se li posa una `'` al
davant perquè Excel el mostri com a text.

Els números escrits com a text ("-12,50", "+34 600 000 000") no es toquen.
Només s'ha de fer servir en fitxers per a persones, no en fitxers que importa
un altre sistema.
"""
import csv
import re

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_NUMERIC_TEXT = re.compile(r"^[+-]?[\d.,\s]+$")


def csv_safe_value(value):
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES) and not _NUMERIC_TEXT.match(value):
        return "'" + value
    return value


def csv_unescape_value(value):
    """
    Inversa de `csv_safe_value`: en importar un CSV que vam exportar nosaltres,
    treu la `'` que hi vam posar perquè el valor es desi tal com era.
    """
    if isinstance(value, str) and value.startswith("'") and value[1:].startswith(_FORMULA_PREFIXES):
        return value[1:]
    return value


class SafeCsvWriter:
    """Com `csv.writer`, però protegeix cada valor amb `csv_safe_value`."""

    def __init__(self, file, *args, **kwargs):
        self._writer = csv.writer(file, *args, **kwargs)

    def writerow(self, row):
        return self._writer.writerow([csv_safe_value(value) for value in row])

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
