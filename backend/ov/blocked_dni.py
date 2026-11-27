"""DNI bloquejats a l'Oficina Virtual.

Hi ha documents genèrics (p. ex. 99999999R, el DNI de reemplaçament) que
comparteixen centenars de fitxes de persones diferents. Una consulta de l'OV
amb un d'aquests DNI exposaria dades de totes aquestes persones, i un tràmit
el lligaria a una fitxa qualsevol. Per això els endpoints de l'OV que reben un
DNI el rebutgen amb un 400 abans de cap consulta.

Només s'aplica a l'OV: la resta del Customers els continua acceptant.
"""

from rest_framework import serializers

from coredata.utils.person_dni_utils import normalize_person_dni

# Llista fixa al codi, comparada amb el DNI normalitzat (sense espais, punts
# ni guions i en majúscules).
OV_BLOCKED_DNIS = frozenset({"99999999R"})

OV_BLOCKED_DNI_ERROR = "DNI not allowed"


def is_ov_blocked_dni(value):
    """Indica si `value`, un cop normalitzat, és un DNI bloquejat a l'OV."""
    return normalize_person_dni(value) in OV_BLOCKED_DNIS


def reject_ov_blocked_dni(value):
    """Validador de camp dels serializers de l'OV: error si el DNI és bloquejat."""
    if is_ov_blocked_dni(value):
        raise serializers.ValidationError(f"{OV_BLOCKED_DNI_ERROR}.")
    return value


class OVBlockedDniQueryMixin:
    """Vistes de l'OV amb el paràmetre `dni` a la query: si és un DNI
    bloquejat, responen 400 `{"error": "DNI not allowed"}` abans d'executar el
    mètode (i després de l'autenticació, els permisos i el límit de crides)."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if is_ov_blocked_dni(request.query_params.get("dni")):
            raise serializers.ValidationError({"error": OV_BLOCKED_DNI_ERROR})
