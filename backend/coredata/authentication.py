"""Autenticació per token amb caducitat.

- Persones: un token de sessió (`AuthSessionToken`) per login, que caduca per
  inactivitat o per antiguitat i es pot revocar amb el logout.
- Integracions (OV, GMAO, Giswater, Smartmetering...): fan servir el token de
  DRF, que caduca als AUTH_INTEGRATION_TOKEN_MAX_AGE_DAYS dies; en tornar a fer
  login se'n genera un de nou. Un token de DRF d'un usuari que no és
  d'integració ja no serveix.

La capçalera continua sent `Authorization: Token <clau>`.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token

from coredata.models import AuthSessionToken

# Com a molt, una escriptura de la darrera activitat per token cada 5 minuts.
LAST_USED_REFRESH = timedelta(minutes=5)


def is_integration_user(user):
    """Usuari d'integració amb token permanent (per nom d'usuari o per grup)."""
    if user.username in settings.AUTH_TOKEN_NON_EXPIRING_USERS:
        return True
    return user.groups.filter(name__in=settings.AUTH_TOKEN_NON_EXPIRING_GROUPS).exists()


def integration_token_is_expired(token, now=None):
    """El token de DRF d'una integració caduca AUTH_INTEGRATION_TOKEN_MAX_AGE_DAYS dies després de crear-lo."""
    now = now or timezone.now()
    return token.created < now - timedelta(days=settings.AUTH_INTEGRATION_TOKEN_MAX_AGE_DAYS)


def issue_token_key(user):
    """Clau de token per a un login: de DRF (renovat si ha caducat) per a integracions, de sessió per a persones."""
    if is_integration_user(user):
        token = Token.objects.filter(user=user).first()
        if token is not None and integration_token_is_expired(token):
            token.delete()
        token, _created = Token.objects.get_or_create(user=user)
        return token.key
    AuthSessionToken.purge_expired(user)
    return AuthSessionToken.create_for(user).key


def revoke_user_tokens(user, except_key=None):
    """Esborra tots els tokens de l'usuari (sessions i token de DRF), excepte el de clau `except_key`."""
    sessions = AuthSessionToken.objects.filter(user=user)
    tokens = Token.objects.filter(user=user)
    if except_key:
        sessions = sessions.exclude(key=except_key)
        tokens = tokens.exclude(key=except_key)
    sessions.delete()
    tokens.delete()


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        session = AuthSessionToken.objects.select_related("user").filter(key=key).first()
        if session is not None:
            return self._authenticate_session(session)

        token = Token.objects.select_related("user").filter(key=key).first()
        if token is None or not is_integration_user(token.user):
            raise exceptions.AuthenticationFailed(_("Invalid token."))
        if integration_token_is_expired(token):
            raise exceptions.AuthenticationFailed(_("Invalid token."))
        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(_("User inactive or deleted."))
        return (token.user, token)

    def _authenticate_session(self, session):
        now = timezone.now()
        if session.is_expired(now):
            session.delete()
            raise exceptions.AuthenticationFailed(_("Invalid token."))
        if not session.user.is_active:
            raise exceptions.AuthenticationFailed(_("User inactive or deleted."))
        if now - session.last_used > LAST_USED_REFRESH:
            AuthSessionToken.objects.filter(pk=session.pk).update(last_used=now)
            session.last_used = now
        return (session.user, session)


def get_user_from_token_key(key):
    """Usuari d'una clau de token vàlida, o None (per a vistes fora de DRF)."""
    if not key:
        return None
    try:
        user, _token = ExpiringTokenAuthentication().authenticate_credentials(key)
    except exceptions.AuthenticationFailed:
        return None
    return user
