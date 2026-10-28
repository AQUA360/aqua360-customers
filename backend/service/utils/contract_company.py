"""Empresa del contracte per als documents i comunicacions generats (logo, colors i signatura).

Amb `use_multiple_companies` el logo, els colors i la signatura són els de l'empresa del
contracte (si en té); si no, els de l'empresa per defecte de cada document (la de la
configuració, la de l'explotació...).
"""
import os

from django.conf import settings

from billing.utils.aca_company_service import use_multiple_companies
from coredata.models import ConfigProject

DEFAULT_MAIN_COLOR = "#074df0"
DEFAULT_SECONDARY_COLOR = "#ffffff"


def get_contract_company(contract):
    """Empresa del contracte si `use_multiple_companies` està actiu; si no, o si no en té, None."""
    if not contract or not use_multiple_companies():
        return None
    return contract.company


def build_logo_path(logo_db):
    """URL (amb DOMAIN_MEDIA) o camí dins de MEDIA_ROOT del logo, o None si no n'hi ha."""
    if not logo_db:
        return None
    # netejem logo_db assegurant-nos que sempre arriba el mateix format, potser que arribi una url o un path que comenci per /media/
    logo_db = f'uploads/{logo_db.split("uploads/")[1]}'
    domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''
    if domain_media:
        return os.path.join(domain_media, f'media/{logo_db}')
    # Fallback a MEDIA_ROOT si DOMAIN_MEDIA no està definit
    return os.path.join(settings.MEDIA_ROOT, logo_db)


def contract_company_logo(contract):
    """Logo de l'empresa del contracte (vegeu `get_contract_company`), o None."""
    company = get_contract_company(contract)
    if company and company.logo:
        return build_logo_path(company.logo.name)
    return None


def _company_color(companies, field, config_token, default):
    for company in companies:
        value = getattr(company, field, None) if company else None
        if value:
            return value
    config = ConfigProject.objects.filter(token=config_token).first()
    return config.value if config and config.value else default


def company_colors(*companies):
    """(color principal, color secundari): el primer que tingui definit alguna de les
    empreses, per ordre; si cap en té, el de ConfigProject i, si no, el per defecte."""
    return (
        _company_color(companies, 'invoice_main_color', 'invoice_main_color', DEFAULT_MAIN_COLOR),
        _company_color(companies, 'invoice_secondary_color', 'invoice_secondary_color', DEFAULT_SECONDARY_COLOR),
    )
