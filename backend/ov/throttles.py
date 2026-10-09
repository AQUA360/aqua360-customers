from rest_framework.throttling import SimpleRateThrottle


class DniEnumerationThrottle(SimpleRateThrottle):
    """
    Rate limit for `GET /ov/contracts/`, which returns contract and holder data
    for an arbitrary DNI supplied in the query string.

    Without a limit the endpoint can be used to enumerate the customer base: a
    caller only has to guess a document number. The throttle bounds how many
    lookups one authenticated OV account can perform, which raises the cost of
    an enumeration run and makes it observable.

    The cache key is the authenticated user rather than the requested DNI: an
    attacker probing the customer base varies the DNI on every call, so a
    per-DNI counter would never trip.

    `.rate` is declared on the class so that no `DEFAULT_THROTTLE_RATES` entry
    -- and therefore no settings change -- is required.

    Note: this uses Django's default cache, which is `LocMemCache` in this
    project, so the counter is held per worker process and the effective limit
    is `rate * GUNICORN_WORKERS`. Pointing `cache` at a shared backend would
    make it exact.
    """

    scope = "ov_contracts_dni"
    rate = "10/min"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            ident = user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
