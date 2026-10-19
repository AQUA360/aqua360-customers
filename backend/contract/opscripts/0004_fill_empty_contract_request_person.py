from django.db.models import F

from contract.models import ContractRequest


def run():
    # Sol·licituds sense sol·licitant: el titular fa de sol·licitant
    updated = ContractRequest.objects.filter(
        person__isnull=True, holder__isnull=False,
    ).update(person=F('holder'))
    print(f"Contract requests with holder as applicant: {updated}")
