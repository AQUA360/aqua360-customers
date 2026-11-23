import re

from django.db.models import Value
from django.db.models.functions import Replace, Upper

_PERSON_DNI_SEPARATORS = re.compile(r"[\s.\-]+")
_PERSON_DNI_SQL_SEPARATORS = ("-", ".", " ", "\t", "\n", "\r", "\xa0")

# DNIs que no identifiquen una persona concreta i es poden repetir
GENERIC_PERSON_TOKENS = ("", "99999999R")


def normalize_person_dni(value):
    """Normalitza un DNI/NIF per comparar-lo amb les dades heretades de la BD:
    ignora espais, guions i punts i el passa a majúscules."""
    return _PERSON_DNI_SEPARATORS.sub("", value or "").upper()


def normalized_dni_expression(field):
    """Expressió SQL equivalent a `normalize_person_dni` per al camp indicat:
    elimina guions, punts i espais (inclosos tabuladors, salts de línia i
    espais no separables) i passa el resultat a majúscules."""
    expression = field
    for separator in _PERSON_DNI_SQL_SEPARATORS:
        expression = Replace(expression, Value(separator), Value(""))
    return Upper(expression)


def person_dni_exists(queryset, dni):
    """Indica si alguna persona del queryset té el mateix DNI normalitzat."""
    return queryset.annotate(
        normalized_token=normalized_dni_expression("token")
    ).filter(normalized_token=normalize_person_dni(dni)).exists()
