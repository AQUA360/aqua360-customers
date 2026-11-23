"""Creació de facturacions a partir d'un facturador.

Si el facturador té `split_by_company`, se'n crea una per a cada empresa proveïdora
d'aigua de l'explotació (amb `Billing.company`); si no, una de sola com fins ara.
"""
import re

from billing.models import Billing, BillingStatus
from service.models import Company


def split_companies_for_biller(biller):
    """Empreses proveïdores d'aigua per a les quals el facturador crea facturació.

    Les de l'explotació del facturador; si no en té, totes les proveïdores actives.
    Una empresa és de l'explotació si hi està vinculada (empresa principal o llista
    d'empreses) o si hi té contractes: la pantalla d'explotació només permet
    informar-ne l'empresa principal.
    """
    from django.db.models import Q
    from contract.models import Contract
    from service.models import Exploitation

    companies = Company.objects.filter(is_active=True, is_provider=True)
    if biller.exploitation_id:
        exploitation_id = biller.exploitation_id
        main_company_ids = Exploitation.objects.filter(id=exploitation_id).values('company_id')
        contract_company_ids = Contract.objects.filter(
            supply_points__connection__exploitation_id=exploitation_id,
            company__isnull=False,
        ).values('company_id')
        companies = companies.filter(
            Q(exploitations__id=exploitation_id)
            | Q(id__in=main_company_ids)
            | Q(id__in=contract_company_ids)
        )
    return list(companies.distinct().order_by('id'))


def company_suffix(company):
    """Sufix curt i estable per al codi de la facturació d'una empresa."""
    raw = (company.alias or '').strip() or str(company.id)
    return re.sub(r'\s+', '_', raw)


def company_label(company):
    return (company.alias or company.name or str(company.id)).strip()


def _with_company(base_token, base_name, company):
    if company is None:
        return base_token, base_name
    return f"{base_token}-{company_suffix(company)}", f"{base_name} - {company_label(company)}"


def _unique(token, name):
    """Afegeix `/n` al codi i al nom fins que el codi no estigui en ús."""
    unique_token, unique_name = token, name
    counter = 1
    while Billing.objects.filter(token=unique_token, is_active=True).exists():
        unique_token = f"{token}/{counter}"
        unique_name = f"{name}/{counter}"
        counter += 1
    return unique_token, unique_name


def billing_targets(biller):
    """Llista d'empreses (o `[None]`) per a les quals cal crear facturació."""
    if not biller.split_by_company:
        return [None]
    return split_companies_for_biller(biller)


def planned_tokens(biller, base_token, base_name):
    """Codis i noms que es crearien (sense desduplicar), per validar-ne la unicitat."""
    return [_with_company(base_token, base_name, company) for company in billing_targets(biller)]


def _billing_routes(biller):
    if biller.routes.exists():
        return biller.routes.all()
    from billing.utils.exploitation_scope import routes_for_exploitation
    return routes_for_exploitation(biller.exploitation_id)


def create_billings_for_biller(biller, base_token, base_name, period_start, period_end, status=None, dedupe=True):
    """Crea la facturació (o una per empresa) del facturador i en retorna la llista.

    Amb `dedupe=False` els codis es fan servir tal qual (el cridador n'ha validat la unicitat).
    """
    status = status or BillingStatus.objects.get(is_default=True)
    routes = list(_billing_routes(biller))
    billings = []
    for company in billing_targets(biller):
        token, name = _with_company(base_token, base_name, company)
        if dedupe:
            token, name = _unique(token, name)
        billing = Billing.objects.create(
            status=status,
            name=name,
            token=token,
            biller=biller,
            company=company,
            period_start=period_start,
            period_end=period_end,
            is_active=True,
        )
        billing.routes.set(routes)
        billings.append(billing)
    return billings
