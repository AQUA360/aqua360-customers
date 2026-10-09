import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from rest_framework.authtoken.models import Token


def root_view(request):
    """Vista per a l'arrel del projecte: retorna una pàgina en blanc."""
    return HttpResponse(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title></title></head><body></body></html>",
        content_type="text/html; charset=utf-8",
    )


def protected_media_view(request, path):
    """
    Serve media files only to authenticated users.
    Accepts the DRF token via:
      - Authorization: Token <token>  header
      - ?token=<token>  query parameter (useful for direct browser navigation)
    """
    user = None

    # 1. Try Authorization header
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Token '):
        raw_token = auth_header.split(' ', 1)[1].strip()
        try:
            token_obj = Token.objects.select_related('user').get(key=raw_token)
            user = token_obj.user
        except Token.DoesNotExist:
            pass

    # 2. Fall back to ?token= query param (browser direct navigation)
    if user is None:
        raw_token = request.GET.get('token', '').strip()
        if raw_token:
            try:
                token_obj = Token.objects.select_related('user').get(key=raw_token)
                user = token_obj.user
            except Token.DoesNotExist:
                pass

    # 3. Fall back to Django session (admin / browsable API)
    if user is None and request.user.is_authenticated:
        user = request.user

    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if not os.path.exists(file_path):
        raise Http404

    content_type, _ = mimetypes.guess_type(file_path)

    # Only allow public file extensions (no PDF, DOCX, etc.)
    PUBLIC_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
    _, ext = os.path.splitext(file_path)
    if ext.lower() not in PUBLIC_EXTENSIONS:
        if user is None or not user.is_active:
            return HttpResponseForbidden("Accés no autoritzat.")

    return FileResponse(open(file_path, 'rb'), content_type=content_type or 'application/octet-stream')
