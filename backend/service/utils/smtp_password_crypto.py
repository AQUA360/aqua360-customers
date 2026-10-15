import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def _get_fernet():
    keys = [key.strip() for key in (settings.SMTP_PASSWORD_ENCRYPTION_KEY or '').split(',') if key.strip()]
    if not keys:
        raise ImproperlyConfigured(
            "Falta SMTP_PASSWORD_ENCRYPTION_KEY al .env: no es poden desar contrasenyes de correu."
        )
    try:
        return MultiFernet([Fernet(key) for key in keys])
    except ValueError as exc:
        raise ImproperlyConfigured("SMTP_PASSWORD_ENCRYPTION_KEY no és una clau Fernet vàlida.") from exc


def encrypt_smtp_password(raw_password):
    return _get_fernet().encrypt(raw_password.encode()).decode()


def decrypt_smtp_password(encrypted_password):
    """Contrasenya en clar o None si no n'hi ha o no es pot desxifrar (clau absent o canviada)."""
    if not encrypted_password:
        return None
    try:
        return _get_fernet().decrypt(encrypted_password.encode()).decode()
    except (ImproperlyConfigured, InvalidToken) as exc:
        logger.error("No s'ha pogut desxifrar la contrasenya SMTP d'un correu: %s", exc)
        return None
