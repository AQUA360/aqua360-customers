from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

# Mida màxima del cos que s'accepta al callback (bytes).
SMS_CALLBACK_MAX_BODY_BYTES = 10 * 1024


class SmsCallbackThrottle(SimpleRateThrottle):
    """
    Límit de crides per IP al callback públic d'SMS.

    Es compta sempre per IP (també si la petició porta credencials), perquè
    l'endpoint és públic i un usuari autenticat no s'ha de poder saltar el
    límit. La IP la resol DRF tenint en compte NUM_PROXIES.
    """

    scope = 'sms_callback'
    rate = '60/min'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request),
        }


def _body_too_large(request):
    """
    Comprova la mida del cos sense llegir-lo si la capçalera ja ho diu.

    Una capçalera Content-Length que no és un número es tracta com a massa
    gran: no es pot saber la mida sense llegir el cos.
    """
    content_length = request.META.get('CONTENT_LENGTH')
    if content_length:
        try:
            return int(content_length) > SMS_CALLBACK_MAX_BODY_BYTES
        except (TypeError, ValueError):
            return True
    return len(request.body) > SMS_CALLBACK_MAX_BODY_BYTES


class SmsCallbackView(APIView):
    """
    Callback públic del proveïdor d'SMS.

    Ara mateix no processa ni desa res: només accepta la notificació. No
    escriu el contingut rebut al registre, limita la mida del cos i el
    nombre de crides per IP.
    """

    permission_classes = [AllowAny]
    throttle_classes = [SmsCallbackThrottle]

    def post(self, request, *args, **kwargs):
        if _body_too_large(request):
            return Response(
                {"error": "El cos de la petició és massa gran."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        return Response({"ok": "ok"}, status=status.HTTP_202_ACCEPTED)
