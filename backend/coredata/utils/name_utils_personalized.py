"""
Plantilla per personalitzar la generació i comprovació de tokens per client.

Si aquest fitxer existeix dins de coredata.utils, name_utils.py farà servir
aquestes funcions en lloc de les per defecte. Podeu modificar només les que
necessiteu; la resta es resol amb import (vegeu name_utils.py).
"""
import inspect

from django.utils import timezone

from coredata.utils.name_utils import generate_token as _default_generate_token


def generate_token(model_class, field='-id', *args, offset=1, **kwargs):
    """Personalitzeu la lògica de generació de token aquí."""

    if model_class.__name__ == "ContractRequest":
        # <exploitation.token><%y%m><correlatiu de 3 xifres, amb zeros a l'esquerra>
        # El correlatiu torna a 001 cada mes i cada explotació.
        exploitation = _exploitation_from_request(_contract_request_payload(kwargs))
        exploitation_token = (
            exploitation.token
            if exploitation and getattr(exploitation, "token", None)
            else "00"
        )
        prefix = f"{exploitation_token}{timezone.localtime().strftime('%y%m')}"
        return _next_prefixed_token(model_class, prefix, offset)

    return _default_generate_token(model_class, field, *args, offset=offset)


def _contract_request_payload(kwargs):
    """Dades per resoldre l'explotació sense canviar qui crida generate_token.

    La vista no passa el punt de subministrament: a l'alta és al body de la
    petició i, en regenerar, a la ContractRequest ja desada.
    """
    explicit = kwargs.get("request_data")
    if explicit:
        return explicit

    request, instance = _caller_request_and_instance()
    if instance is not None and instance.__class__.__name__ == "ContractRequest":
        supply_point_ids = list(instance.supply_points.values_list("pk", flat=True))
        if instance.supply_point_default_id:
            supply_point_ids.insert(0, instance.supply_point_default_id)
        return {
            "supply_point_ids": supply_point_ids,
            "type": instance.type_id,
        }

    data = getattr(request, "data", None) if request is not None else None
    return data or {}


def _caller_request_and_instance():
    request = None
    instance = None
    frame = inspect.currentframe()
    try:
        frame = frame.f_back
        while frame is not None:
            locs = frame.f_locals
            if request is None and hasattr(locs.get("request"), "data"):
                request = locs["request"]
            candidate = locs.get("instance")
            if (
                instance is None
                and candidate is not None
                and candidate.__class__.__name__ == "ContractRequest"
            ):
                instance = candidate
            if request is not None and instance is not None:
                break
            frame = frame.f_back
    finally:
        del frame
    return request, instance


def _exploitation_from_request(request_data):
    """Explotació del primer punt de subministrament, o la del tipus de sol·licitud."""
    from service.models import SupplyPoint

    supply_point_ids = _as_id_list(
        request_data.get("supply_point_ids")
        or request_data.get("supply_points")
        or request_data.get("supply_point_id")
        or request_data.get("supply_point_default")
    )
    if supply_point_ids:
        sp = (
            SupplyPoint.objects
            .filter(pk=supply_point_ids[0])
            .select_related("connection__exploitation")
            .first()
        )
        if sp and getattr(sp, "connection", None):
            exploitation = getattr(sp.connection, "exploitation", None)
            if exploitation:
                return exploitation

    type_id = request_data.get("type")
    if type_id:
        from contract.models import ContractRequestType
        cr_type = (
            ContractRequestType.objects
            .filter(pk=type_id)
            .select_related("exploitation")
            .first()
        )
        if cr_type and getattr(cr_type, "exploitation", None):
            return cr_type.exploitation

    return None


def _as_id_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple)):
        return [item for item in value if item not in (None, "")]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def _next_prefixed_token(model_class, prefix, offset):
    max_seq = 0
    prefix_len = len(prefix)
    for token in model_class.objects.filter(token__startswith=prefix).values_list("token", flat=True):
        suffix = token[prefix_len:]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))

    seq = max_seq + offset
    while True:
        candidate = f"{prefix}{seq:03d}"
        if not model_class.objects.filter(token=candidate).exists():
            return candidate
        seq += 1
