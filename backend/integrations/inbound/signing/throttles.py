from rest_framework.throttling import SimpleRateThrottle


class SigningCallbackThrottle(SimpleRateThrottle):
    """Límit per IP del callback de signatura, que és públic (la clau es comprova dins la vista).

    Aqua360 Sign hi fa unes poques crides per document signat; el límit només talla les
    ràfegues d'un tercer. `rate` és a la classe perquè no cal cap entrada a
    DEFAULT_THROTTLE_RATES. El comptador és per procés (LocMemCache), igual que els de l'OV."""

    scope = "signing_callback"
    rate = "60/min"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
