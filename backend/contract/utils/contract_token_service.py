import logging

from coredata.models import ConfigProject
from coredata.utils import name_utils
from coredata.utils.name_utils import generate_token, check_token_exists

logger = logging.getLogger(__name__)

CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED_TOKEN = 'CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED'


def is_contract_token_generation_incremental_enabled():
    """
    Retorna si la generació incremental del codi de contracte (a partir del
    darrer Contract, ignorant la data) està habilitada, segons el ConfigProject
    amb token `CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED`. Deshabilitat per
    defecte: es manté el comportament basat en data (generate_token).
    """
    config = ConfigProject.objects.filter(token=CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED_TOKEN).first()
    if not config or not config.value:
        return False
    return config.value.lower() == 'true'


def generate_contract_request_token():
    """Genera el token d'una nova ContractRequest.

    Si `CONTRACT_TOKEN_GENERATION_INCREMENTAL_ENABLED` és 'true', continua la
    numeració a partir del token numèric del darrer Contract (el més nou),
    ignorant la data. Si no, manté el comportament actual basat en data
    (generate_token).
    """
    from contract.models import Contract, ContractRequest

    if is_contract_token_generation_incremental_enabled():
        last_contract = Contract.objects.filter(token__regex=r'^\d+$').order_by('-id').first()
        if last_contract:
            next_number = int(last_contract.token) + 1
            token = f'{next_number:0{len(last_contract.token)}d}'
            return check_token_exists(token, ContractRequest)

    return check_token_exists(generate_token(ContractRequest), ContractRequest)


def contract_request_token_kwargs(instance):
    """Dades de la ContractRequest que poden determinar el seu token, amb el
    format que reben generate_token i contract_request_token_matches de
    name_utils_personalized."""
    supply_point_ids = list(instance.supply_points.values_list('pk', flat=True))
    if instance.supply_point_default_id:
        if instance.supply_point_default_id in supply_point_ids:
            supply_point_ids.remove(instance.supply_point_default_id)
        supply_point_ids.insert(0, instance.supply_point_default_id)
    return {
        'use_type_id': instance.use_type_id,
        'client_type_id': instance.client_type_id,
        'company_id': instance.company_id,
        'is_change_of_name': instance.is_change_of_name,
        'request_data': {
            'supply_point_ids': supply_point_ids,
            'type': instance.type_id,
        },
    }


def next_contract_request_token(instance, token_kwargs=None):
    """Calcula (sense desar-lo) un token nou per a una ContractRequest existent,
    evitant col·lisions amb altres sol·licituds."""
    from contract.models import ContractRequest

    if token_kwargs is None:
        token_kwargs = contract_request_token_kwargs(instance)
    candidate = generate_token(ContractRequest, **token_kwargs)

    while ContractRequest.objects.filter(token=candidate).exclude(pk=instance.pk).exists():
        try:
            candidate = f'{int(candidate) + 1:0{len(candidate)}d}'
        except (TypeError, ValueError):
            candidate = check_token_exists(candidate, ContractRequest)
            break
    return candidate


def _is_contract_request_closed(instance):
    """Sol·licitud finalitzada o cancel·lada."""
    status_token = getattr(instance.status, 'token', None)
    if status_token is None:
        return False
    config = dict(
        ConfigProject.objects
        .filter(token__in=['contract_request_finalize_token', 'contract_request_cancel_token'])
        .values_list('token', 'value')
    )
    closed_tokens = {
        config.get('contract_request_finalize_token') or '3',
        config.get('contract_request_cancel_token'),
    }
    return str(status_token) in {str(t) for t in closed_tokens if t}


def sync_contract_request_token(instance):
    """Regenera i desa el token d'una ContractRequest oberta només si les dades
    que el determinen han canviat de manera que el token actual ja no hi
    correspon.

    Només actua si name_utils_personalized defineix contract_request_token_matches;
    sense personalització (o sense aquesta funció) el token no es toca mai.

    Retorna (token, changed).
    """
    matches = name_utils.contract_request_token_matches
    if matches is None:
        return instance.token, False
    if _is_contract_request_closed(instance):
        return instance.token, False
    if instance.is_change_of_name and instance.keep_same_code:
        # En finalitzar es reutilitza el codi del contracte anterior
        return instance.token, False

    token_kwargs = contract_request_token_kwargs(instance)
    if instance.token and matches(instance.token, **token_kwargs):
        return instance.token, False

    old_token = instance.token
    new_token = next_contract_request_token(instance, token_kwargs)
    if new_token == old_token:
        return instance.token, False

    instance.token = new_token
    instance.save(update_fields=['token'])
    logger.info('ContractRequest %s: token regenerat (%s -> %s)', instance.pk, old_token, new_token)
    return new_token, True
