from collections import defaultdict
from decimal import Decimal


def person_debt_amounts_by_person_id(person_ids):
    """Deute per persona = suma del deute (vw_contract_debt) dels contractes on és titular."""
    # Import dins la funció per evitar imports circulars entre coredata i contract
    from contract.models import Contract
    from contract.utils.contract_list_queryset import contract_debt_amounts_by_contract_id

    person_ids = [pid for pid in person_ids if pid]
    if not person_ids:
        return {}

    rows = list(
        Contract.objects.filter(holder_id__in=person_ids).values_list('id', 'holder_id')
    )
    debt_by_contract = contract_debt_amounts_by_contract_id([cid for cid, _ in rows])

    result = defaultdict(lambda: Decimal('0'))
    for contract_id, person_id in rows:
        result[person_id] += debt_by_contract.get(contract_id, Decimal('0'))
    return result