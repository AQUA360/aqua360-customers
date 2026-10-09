from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token, check_token_exists

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
