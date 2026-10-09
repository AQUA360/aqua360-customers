from coredata.models import ConfigProject
from service.models import Company


class ACACompanyError(Exception):
    """La selecció no permet saber de quina empresa és el fitxer ACA. Es mostra a l'usuari tal qual."""


def use_multiple_companies():
    config = ConfigProject.objects.filter(token='use_multiple_companies').first()
    return bool(config and config.value and config.value.lower() == 'true')


def get_records_company(company_ids, records_label='factures'):
    """Empresa comuna a tots els registres (factures, contractes...) que entren en un fitxer ACA.

    Un fitxer ACA el declara una sola entitat subministradora, així que registres de més
    d'una empresa, o sense empresa, no es poden declarar junts. Retorna None si no n'hi ha cap.
    """
    company_ids = set(company_ids)
    if not company_ids:
        return None
    if None in company_ids:
        raise ACACompanyError(
            f"Hi ha {records_label} sense empresa assignada: no es pot saber amb quin codi d'entitat "
            "subministradora s'han de declarar."
        )
    if len(company_ids) > 1:
        names = Company.objects.filter(id__in=company_ids).order_by('name').values_list('name', flat=True)
        raise ACACompanyError(
            f"Hi ha {records_label} de més d'una empresa (" + ", ".join(n or '-' for n in names) + "). "
            "Cal generar un fitxer per empresa."
        )
    return Company.objects.get(id=company_ids.pop())


def resolve_aca_company(company_ids, default_company, records_label='factures'):
    """Empresa declarant d'un fitxer ACA, de la qual surten el codi d'entitat subministradora
    (supply_code) i el NIF.

    Amb `use_multiple_companies` és l'empresa dels registres del fitxer (han de ser totes la
    mateixa); si no, o si el fitxer no té cap registre, `default_company` (la de
    'main_company_token').
    """
    company = None
    if use_multiple_companies():
        company = get_records_company(company_ids, records_label)
    company = company or default_company

    if not company or not company.supply_code:
        raise ACACompanyError(
            "Falta configurar el codi d'entitat subministradora (supply_code) de l'empresa "
            + ((company.name or str(company.id)) if company else "principal ('main_company_token')")
        )
    return company
