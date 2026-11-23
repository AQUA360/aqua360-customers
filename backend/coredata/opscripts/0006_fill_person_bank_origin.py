"""Omple l'origen (`PersonBank.origin`) dels IBAN existents.

La migració deixa tots els comptes com a històrics (HIST). Aquest script en marca com a OV
els que van entrar per l'Oficina Virtual: els que un usuari del grup `ov` va posar com a
nou pagament d'un contracte (`ContractDataChange.new_payment`). Els IBAN de les altes de
l'OV anteriors a aquest canvi no deixen cap traça fiable i es queden com a HIST.
"""
from contract.models import ContractDataChange
from coredata.models import PersonBank


def run():
    ov_bank_ids = (
        ContractDataChange.objects
        .filter(new_payment__isnull=False, user__groups__name='ov')
        .values_list('new_payment_id', flat=True)
        .distinct()
    )
    marked = PersonBank.objects.filter(
        id__in=list(ov_bank_ids), origin=PersonBank.ORIGIN_HIST,
    ).update(origin=PersonBank.ORIGIN_OV)

    print(f"Comptes bancaris marcats com a OV: {marked}")
    print(f"Comptes bancaris que es queden com a HIST: {PersonBank.objects.filter(origin=PersonBank.ORIGIN_HIST).count()}")
