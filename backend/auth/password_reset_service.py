"""Recuperació de la contrasenya des del login: enllaç per correu amb un token d'un sol ús.

El correu només s'envia si l'usuari existeix, és actiu, no és d'integració i té correu, i si
l'empresa per defecte té el correu configurat. `request_password_reset` torna el resultat real
(per al log i els tests), però la vista sempre respon el mateix: així no es pot saber des de
fora quins usuaris existeixen o tenen correu. La pantalla diu que, si no arriba el correu,
s'adrecin a l'administrador.
"""
import logging
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import get_language, gettext

from coredata.authentication import is_integration_user
from coredata.utils.template_utils import build_template_candidates

logger = logging.getLogger(__name__)

STATUS_SENT = 'sent'
STATUS_UNAVAILABLE = 'unavailable'

RESET_PATH = '/auth/reset-password'
EMAIL_TEMPLATE = 'password_reset_email.html'
MSGRAPH_BACKEND = 'msgraphbackend.MSGraphBackend'


def get_recovery_company():
    """Empresa que envia el correu: la per defecte o, si no n'hi ha, la primera activa."""
    from service.models import Company

    companies = Company.objects.filter(is_active=True).select_related('config')
    return companies.filter(is_default=True).first() or companies.order_by('id').first()


def get_mail_sender(company):
    """(config, correu de configuració, remitent) si l'empresa pot enviar correus; si no, None.

    Mateixos criteris que l'enviament de comunicacions (communication_service.send_electronic_mail).
    """
    config = getattr(company, 'config', None) if company else None
    if config is None:
        return None
    emails = config.company_config_emails.filter(is_active=True)
    config_email = emails.filter(is_default=True).first() or emails.order_by('id').first()
    if config_email is None:
        return None
    from_email = config_email.mail_send_user or config_email.mail_send_mail
    if not from_email:
        return None
    if getattr(settings, 'EMAIL_BACKEND', '') != MSGRAPH_BACKEND:
        if not config.mail_send_smtp_server or not config.mail_send_smtp_port or not config_email.mail_send_mail:
            return None
    return config, config_email, from_email


def get_frontend_base_url(request):
    """Adreça de l'aplicació per a l'enllaç del correu.

    FRONTEND_URL si està configurada; si no, l'Origin de la petició només si és un dels
    CSRF_TRUSTED_ORIGINS. Mai una adreça que vingui del client sense validar: un enllaç amb el
    token cap a un domini d'un tercer li donaria la contrasenya.
    """
    configured = (getattr(settings, 'FRONTEND_URL', '') or '').strip().rstrip('/')
    if configured:
        return configured
    origin = (request.headers.get('Origin') or '').strip().rstrip('/')
    if not origin:
        return None
    trusted = {o.strip().rstrip('/') for o in getattr(settings, 'CSRF_TRUSTED_ORIGINS', []) if o.strip()}
    parts = urlsplit(origin)
    if parts.scheme in ('http', 'https') and parts.netloc and origin in trusted:
        return origin
    return None


def _find_user(username):
    if not username:
        return None
    user = User.objects.filter(username=username).first()
    if user is None or not user.is_active or not user.has_usable_password():
        return None
    if not (user.email or '').strip() or is_integration_user(user):
        return None
    return user


def build_reset_link(base_url, user):
    query = urlencode({
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': default_token_generator.make_token(user),
    })
    return f"{base_url}{RESET_PATH}?{query}"


def _send(company, sender, user, link):
    from communication.utils.communication_service import _send_via_msgraph, _send_via_smtp

    config, config_email, from_email = sender
    lang = get_language()
    timeout_minutes = max(1, settings.PASSWORD_RESET_TIMEOUT // 60)
    html = render_to_string(build_template_candidates(EMAIL_TEMPLATE, lang=lang), {
        'user': user,
        'company_name': company.name or '',
        'link': link,
        'timeout_minutes': timeout_minutes,
    })
    subject = gettext("Password recovery")
    if company.name:
        subject = f"{subject} - {company.name}"
    if getattr(settings, 'EMAIL_BACKEND', '') == MSGRAPH_BACKEND:
        _send_via_msgraph([user.email], subject, html, from_email, [])
    else:
        _send_via_smtp([user.email], subject, html, from_email, [], config, config_email)


def request_password_reset(username, request):
    """Envia el correu de recuperació si es pot; torna STATUS_SENT o STATUS_UNAVAILABLE."""
    user = _find_user((username or '').strip())
    if user is None:
        # Sense el nom d'usuari: el log no ha de servir de llista d'usuaris provats
        logger.info("Recuperació de contrasenya no enviada: usuari inexistent, inactiu, sense correu o d'integració")
        return STATUS_UNAVAILABLE
    company = get_recovery_company()
    sender = get_mail_sender(company)
    base_url = get_frontend_base_url(request)
    if sender is None or base_url is None:
        logger.warning(
            "Recuperació de contrasenya no disponible: correu de l'empresa %s, adreça de l'aplicació %s",
            'configurat' if sender else 'no configurat', 'coneguda' if base_url else 'desconeguda',
        )
        return STATUS_UNAVAILABLE
    try:
        _send(company, sender, user, build_reset_link(base_url, user))
    except Exception:
        # El detall (codi SMTP...) només al log; a la pantalla, que s'adreci a l'administrador
        logger.exception("No s'ha pogut enviar el correu de recuperació de contrasenya de l'usuari %s", user.pk)
        return STATUS_UNAVAILABLE
    logger.info("Correu de recuperació de contrasenya enviat a l'usuari %s", user.pk)
    return STATUS_SENT


def get_user_from_reset_token(uid, token, for_update=False):
    """L'usuari si el token és vàlid (no caducat, no fet servir); si no, None.

    `for_update`: bloqueja la fila de l'usuari (cal una transacció) per gastar el token de
    manera atòmica."""
    try:
        pk = force_str(urlsafe_base64_decode(uid or ''))
        users = User.objects.select_for_update() if for_update else User.objects
        user = users.get(pk=pk, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if not token or not default_token_generator.check_token(user, token):
        return None
    return user
