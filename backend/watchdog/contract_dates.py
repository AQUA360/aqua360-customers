from django.db.models import F
from django.db.models.functions import Coalesce, TruncDate

from billing.models import Reading
from contract.models import ContractStatus


def contract_effective_date(contract):
    """Data de referència del contracte: registration_date o, si és buida, created_at."""
    if contract.registration_date:
        return contract.registration_date
    if contract.created_at:
        return contract.created_at.date()
    return None


def contract_effective_date_source(contract):
    if contract.registration_date:
        return "registration_date"
    return "created_at"


def active_contract_status():
    from coredata.models import ConfigProject

    config = ConfigProject.objects.get(token="contract_active_token")
    return ContractStatus.objects.get(token=config.value)


def readings_before_contract_effective_date(active_status):
    return (
        Reading.objects.filter(
            contract__status=active_status,
            contract__isnull=False,
            reading_date__isnull=False,
        )
        .annotate(
            contract_effective_date=Coalesce(
                "contract__registration_date",
                TruncDate("contract__created_at"),
            )
        )
        .filter(reading_date__lt=F("contract_effective_date"))
        .select_related("contract")
    )
