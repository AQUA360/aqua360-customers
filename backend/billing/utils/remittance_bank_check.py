"""
Comprovació de les dades del compte de l'empresa abans de generar una remesa.

El fitxer SEPA (rebuts i transferències de retorn) porta l'IBAN, el BIC i
l'identificador de creditor del compte amb què es remesa, i el nom i el NIF de
l'empresa titular. Si en falta alguna, el fitxer surt igualment però el banc el
rebutja amb un error que no diu què falta. Per això es comprova abans de
generar-lo i es diu a l'usuari què ha d'omplir i on.
"""
import re

from django.utils.translation import gettext as _
from schwifty import IBAN
from schwifty.exceptions import SchwiftyException

# Patró del BIC a l'XSD de pain.001.001.03 i pain.008.001.02 (BICIdentifier).
BIC_PATTERN = re.compile(r'^[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3})?$')

ISSUE_NO_COMPANY = 'no_company'
ISSUE_COMPANY_NAME = 'company_name'
ISSUE_COMPANY_VAT = 'company_vat'
ISSUE_IBAN = 'iban'
ISSUE_INVALID_IBAN = 'invalid_iban'
ISSUE_BIC = 'bic'
ISSUE_INVALID_BIC = 'invalid_bic'
ISSUE_CREDITOR_ID = 'creditor_id'


class RemittanceBankDataError(ValueError):
    """Un o més comptes de la remesa no tenen les dades que demana el fitxer SEPA."""

    def __init__(self, bank_issues):
        self.bank_issues = bank_issues
        super().__init__(' '.join(item['message'] for item in bank_issues))


def normalize_account_code(value):
    """IBAN o BIC sense espais ni guions i en majúscules, com els vol l'XSD."""
    return re.sub(r'[\s-]', '', value or '').upper()


def get_company_bank_issues(company_bank):
    """
    Torna la llista de codis del que falta o no és vàlid al compte
    `company_bank` per poder generar el fitxer SEPA. Buida si tot és correcte.
    Els rebuts i les transferències fan servir les mateixes dades del compte.
    """
    issues = []
    company = company_bank.company
    if not company:
        issues.append(ISSUE_NO_COMPANY)
    else:
        if not (company.alias or '').strip():
            issues.append(ISSUE_COMPANY_NAME)
        if not (company.vat or '').strip():
            issues.append(ISSUE_COMPANY_VAT)

    iban = normalize_account_code(company_bank.iban)
    if not iban:
        issues.append(ISSUE_IBAN)
    else:
        try:
            IBAN(iban)
        except SchwiftyException:
            issues.append(ISSUE_INVALID_IBAN)

    bic = normalize_account_code(company_bank.swift)
    if not bic:
        issues.append(ISSUE_BIC)
    elif not BIC_PATTERN.match(bic):
        issues.append(ISSUE_INVALID_BIC)

    if not (company_bank.sepa_cred_identifier or '').strip():
        issues.append(ISSUE_CREDITOR_ID)
    return issues


def describe_company_bank(company_bank):
    """Nom curt del compte per als missatges: entitat i darrers dígits de l'IBAN."""
    bank_name = company_bank.bank.name if company_bank.bank and company_bank.bank.name else None
    iban = normalize_account_code(company_bank.iban)
    parts = [bank_name or _("bank account")]
    if iban:
        parts.append(f"(...{iban[-4:]})")
    return ' '.join(parts)


def _issue_label(code):
    labels = {
        ISSUE_COMPANY_NAME: _("company name"),
        ISSUE_COMPANY_VAT: _("company tax ID (NIF)"),
        ISSUE_IBAN: _("IBAN"),
        ISSUE_INVALID_IBAN: _("a valid IBAN (the current one is not correct)"),
        ISSUE_BIC: _("BIC/SWIFT"),
        ISSUE_INVALID_BIC: _("a valid BIC/SWIFT (the current one is not correct)"),
        ISSUE_CREDITOR_ID: _("SEPA creditor identifier"),
    }
    return labels[code]


def company_bank_issues_message(company_bank, issues):
    """Missatge per a l'usuari: quin compte és, què li falta i on s'omple."""
    account = describe_company_bank(company_bank)
    if ISSUE_NO_COMPANY in issues:
        return _(
            "The account {account} is not linked to any company. "
            "Assign it to a company before generating the remittance."
        ).format(account=account)
    fields = ', '.join(_issue_label(code) for code in issues)
    return _(
        "The account {account} of {company} is missing: {fields}. "
        "Fill it in in the company's bank details and search again."
    ).format(account=account, company=company_bank.company.alias or '', fields=fields)


def get_company_banks_issues(company_banks):
    """
    `[{bank, bank_name, company_name, issues, message}]` dels comptes de
    `company_banks` que tenen dades que falten, en el mateix ordre.
    """
    result = []
    for company_bank in company_banks:
        issues = get_company_bank_issues(company_bank)
        if not issues:
            continue
        result.append({
            'bank': company_bank.id,
            'bank_name': company_bank.bank.name if company_bank.bank else None,
            'company_name': company_bank.company.alias if company_bank.company else None,
            'issues': issues,
            'message': company_bank_issues_message(company_bank, issues),
        })
    return result


def check_company_banks(company_banks):
    """Llança `RemittanceBankDataError` si algun compte no té les dades que calen."""
    bank_issues = get_company_banks_issues(company_banks)
    if bank_issues:
        raise RemittanceBankDataError(bank_issues)
