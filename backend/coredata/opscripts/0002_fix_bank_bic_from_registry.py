"""Corregeix els BIC truncats del catàleg de bancs i dels comptes que els han copiat.

El catàleg `coredata.Bank` (fixture `initial_data/*/coredata.Banks.json`) només porta el
codi d'entitat de 4 lletres al camp `bic` ("BSAB" en lloc de "BSABESBB"), que no és un BIC
vàlid. El frontal copiava aquest valor al `swift` dels comptes en detectar el banc des de
l'IBAN, i la remesa SEPA l'acabava completant a cegues amb "ESMMXXX" (`sepa_file_service`).

- `Bank.bic`: es posa el BIC oficial del registre del Banc d'Espanya que porta schwifty.
  Els codis que no hi surten es deixen com estan.
- `PersonBank.swift` / `CompanyBank.swift`: només es toquen els comptes amb IBAN espanyol i
  un SWIFT que no té 8 ni 11 caràcters (els valors correctes i els buits no es toquen).

`bulk_update` a propòsit: el `post_save` de PersonBank (`assign_bank`) no ha de saltar.
"""
from coredata.models import Bank, PersonBank
from coredata.utils.iban_validator_utils import get_spanish_bic
from service.models import CompanyBank

VALID_BIC_LENGTHS = (8, 11)


def _fix_bank_catalog():
    to_update = []
    for bank in Bank.objects.exclude(token__isnull=True).exclude(token='').iterator(chunk_size=500):
        bic = get_spanish_bic(bank.token)
        if bic and (bank.bic or '').strip() != bic:
            bank.bic = bic
            to_update.append(bank)
    Bank.objects.bulk_update(to_update, ['bic'], batch_size=500)
    print(f"Bank.bic corregits: {len(to_update)}")


def _fix_account_swifts(model):
    to_update = []
    queryset = model.objects.filter(iban__istartswith='ES').exclude(swift__isnull=True).exclude(swift='')
    for account in queryset.only('id', 'iban', 'swift').iterator(chunk_size=500):
        if len(account.swift.strip()) in VALID_BIC_LENGTHS:
            continue
        iban = account.iban.replace(' ', '').upper()
        bic = get_spanish_bic(iban[4:8])
        if bic:
            account.swift = bic
            to_update.append(account)
    model.objects.bulk_update(to_update, ['swift'], batch_size=500)
    print(f"{model.__name__}.swift corregits: {len(to_update)}")


def run():
    _fix_bank_catalog()
    _fix_account_swifts(PersonBank)
    _fix_account_swifts(CompanyBank)
