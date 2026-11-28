"""Regles per als fitxers que arriben a les ordres: pujats pels usuaris o baixats del GMAO.

Només s'accepten imatges i PDF, de mida limitada, i el contingut ha de ser el que diu
l'extensió. El nom que arriba mai es fa servir tal com ve: es queda amb l'últim tros i
només amb caràcters segurs.
"""
import os
import re
from urllib.parse import urlsplit

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_FILE_NAME_LENGTH = 100

# extensió -> inici (signatura) que ha de tenir el fitxer
SIGNATURES = {
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.gif': (b'GIF87a', b'GIF89a'),
    '.webp': (b'RIFF',),
    '.pdf': (b'%PDF-',),
}
ALLOWED_EXTENSIONS = tuple(SIGNATURES)


class UploadRejected(ValueError):
    """El fitxer no compleix les regles; el missatge es pot mostrar a l'usuari."""


def safe_file_name(name):
    base = os.path.basename((name or '').replace('\\', '/'))
    base = re.sub(r'[^\w.\- ()]', '_', base).strip('. ')
    if len(base) > MAX_FILE_NAME_LENGTH:
        stem, ext = os.path.splitext(base)
        base = stem[:MAX_FILE_NAME_LENGTH - len(ext)] + ext
    return base


def validate_file(name, head, size):
    """Valida el nom, la mida i l'inici del contingut. Retorna el nom net."""
    clean = safe_file_name(name)
    ext = os.path.splitext(clean)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadRejected('Només s\'admeten imatges (jpg, png, gif, webp) i PDF.')
    if size is not None and size > MAX_UPLOAD_BYTES:
        raise UploadRejected(f'El fitxer supera la mida màxima ({MAX_UPLOAD_BYTES // (1024 * 1024)} MB).')
    if not any(head.startswith(signature) for signature in SIGNATURES[ext]):
        raise UploadRejected('El contingut del fitxer no coincideix amb la seva extensió.')
    if ext == '.webp' and head[8:12] != b'WEBP':
        raise UploadRejected('El contingut del fitxer no coincideix amb la seva extensió.')
    return clean


def validate_uploaded_file(uploaded):
    """Valida un fitxer pujat (UploadedFile de Django). Retorna el nom net."""
    head = uploaded.read(16)
    uploaded.seek(0)
    return validate_file(uploaded.name, head, uploaded.size)


def resolve_gmao_url(url, gmao_host):
    """URL completa d'un fitxer del GMAO, o None si no és del servidor del GMAO.

    Un camí relatiu (`/media/...`) es penja del host del GMAO. Una URL absoluta només es
    accepta si és del mateix servidor (esquema, host i port): el missatge no pot fer que
    l'aplicació demani una adreça qualsevol (ni interna).
    """
    if not isinstance(url, str) or not url.strip() or len(url) > 1000:
        return None
    url = url.strip()
    host = urlsplit((gmao_host or '').strip())
    if not host.scheme or not host.netloc:
        return None
    if url.startswith('//') or '\\' in url or any(ord(char) < 32 for char in url):
        return None
    parts = urlsplit(url)
    if parts.scheme or parts.netloc:
        if (parts.scheme, parts.netloc.lower()) != (host.scheme, host.netloc.lower()):
            return None
        path = parts.path
    else:
        path = '/' + url.lstrip('/').split('?')[0].split('#')[0]
    if '..' in path.split('/'):
        return None
    return f"{host.scheme}://{host.netloc}{path}"


USERNAME_PATTERN = re.compile(r'^[\w.@+\-]{1,100}$')


def valid_username(value):
    """Nom d'usuari del GMAO: només caràcters segurs, que acaba en el token d'un operari."""
    return isinstance(value, str) and bool(USERNAME_PATTERN.match(value))


def clean_text(value, max_length):
    """Text lliure d'un missatge: si no és text, buit; si és massa llarg, es talla."""
    if not isinstance(value, str):
        return ''
    return value[:max_length]
