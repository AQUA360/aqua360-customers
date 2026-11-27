import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden

from coredata.authentication import get_user_from_token_key


def root_view(request):
    """Vista per a l'arrel del projecte: retorna una pàgina en blanc."""
    return HttpResponse(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title></title></head><body></body></html>",
        content_type="text/html; charset=utf-8",
    )


# Carpetes de MEDIA_ROOT que es poden servir sense autenticació: els logos i imatges de
# l'empresa (QR, signatura, oficina virtual) i els logos de les explotacions. Els PDF i
# els correus les carreguen per URL (DOMAIN_MEDIA), sense cap credencial.
PUBLIC_MEDIA_PREFIXES = ('uploads/logo/', 'uploads/exploitation/')
PUBLIC_MEDIA_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


def _is_public_media(relative_path):
    _, ext = os.path.splitext(relative_path)
    return relative_path.startswith(PUBLIC_MEDIA_PREFIXES) and ext.lower() in PUBLIC_MEDIA_EXTENSIONS


def _media_user(request):
    """Usuari de la petició: capçalera `Authorization: Token <token>` o sessió de Django.

    El token no s'accepta a la URL (`?token=`): quedaria als registres i a l'historial.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Token '):
        user = get_user_from_token_key(auth_header.split(' ', 1)[1].strip())
        if user is not None:
            return user
    # El middleware deixa request.user a None si el token és invàlid o ha caducat.
    session_user = getattr(request, 'user', None)
    if session_user is not None and session_user.is_authenticated:
        return session_user
    return None


def protected_media_view(request, path):
    """Serveix els fitxers de MEDIA_ROOT: només els de PUBLIC_MEDIA_PREFIXES sense
    autenticació; la resta (fotos de lectures, documents, plànols...) a usuaris actius."""
    # La ruta no pot sortir de MEDIA_ROOT (p. ex. amb '..' o una ruta absoluta).
    media_root = os.path.abspath(settings.MEDIA_ROOT)
    file_path = os.path.normpath(os.path.join(media_root, path))
    if not file_path.startswith(media_root + os.sep):
        raise Http404

    # L'autenticació es comprova abans que l'existència: si no, el 404/403 diria a
    # qualsevol quins fitxers hi ha.
    relative_path = os.path.relpath(file_path, media_root).replace(os.sep, '/')
    if not _is_public_media(relative_path):
        user = _media_user(request)
        if user is None or not user.is_active:
            return HttpResponseForbidden("Accés no autoritzat.")

    if not os.path.isfile(file_path):
        raise Http404

    content_type, _ = mimetypes.guess_type(file_path)
    return FileResponse(open(file_path, 'rb'), content_type=content_type or 'application/octet-stream')
