"""
Enviament de correus interns als usuaris de l'aplicació (no als abonats).

Fa servir la mateixa configuració de correu que les comunicacions: el
CompanyConfig que tingui un correu per defecte (o el primer), i el backend
configurat a EMAIL_BACKEND (SMTP o Microsoft Graph).
"""
from django.conf import settings

from service.models import CompanyConfig


def _company_config():
    """Return a company with default email settings, or any configured email."""
    return (
        CompanyConfig.objects.filter(company_config_emails__is_default=True).distinct().first()
        or CompanyConfig.objects.filter(company_config_emails__isnull=False).distinct().first()
    )


def send_staff_email(to, subject, html_content, attachments=None):
    """
    Envia un correu HTML, amb adjunts PDF opcionals [(nom, bytes)]. Llança una
    excepció si no es pot enviar. També el fan servir els avisos a l'abonat de
    les incidències (justificant i enquesta), amb la mateixa configuració de correu.
    """
    from communication.utils.communication_service import (
        _send_via_msgraph, _send_via_smtp, get_smtp_config_email,
    )

    recipients = [to] if isinstance(to, str) else list(to)
    comm_config = _company_config()
    if not comm_config:
        raise Exception("No company configuration with email found")

    config_email = get_smtp_config_email(comm_config)
    from_email = config_email.mail_send_user or config_email.mail_send_mail if config_email else None
    if not from_email:
        raise Exception("No sender email address found")

    if getattr(settings, "EMAIL_BACKEND", "") == "msgraphbackend.MSGraphBackend":
        _send_via_msgraph(recipients, subject, html_content, from_email, attachments or [])
    else:
        _send_via_smtp(recipients, subject, html_content, from_email, attachments or [], comm_config, config_email)
