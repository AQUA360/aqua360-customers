from django.http import JsonResponse
from rest_framework.authentication import TokenAuthentication


class RestrictOVUserMiddleware:
    """
    Restrict Django users that belong to scoped integration groups.

    - group ``ov`` → only ``/ov/`` (and ``/api/ov/`` if API_URL_PREFIX)
    - group ``giswater`` → only ``/giswater/`` (and ``/api/giswater/``)
    - group ``smartmetering`` → only ``/smartmetering/`` (and ``/api/smartmetering/``)

    Other authenticated users are unaffected. Apps with custom auth are exempt.
    """

    # group name → path prefixes they may access
    RESTRICTED_GROUPS = {
        "ov": ("/ov/",),
        "giswater": ("/giswater/",),
        "smartmetering": ("/smartmetering/",),
    }

    def __init__(self, get_response):
        self.get_response = get_response
        self.auth = TokenAuthentication()
        # Paths that use their own custom authentication (don't require Django auth)
        self.exempt_paths = ["/got/", "/lecturapp/"]

    def __call__(self, request):
        for exempt_path in self.exempt_paths:
            if self._path_matches(request.path, exempt_path):
                return self.get_response(request)

        try:
            user_auth_tuple = self.auth.authenticate(request)
            if user_auth_tuple is not None:
                request.user, _ = user_auth_tuple
        except Exception:
            request.user = None

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            for group_name, allowed_prefixes in self.RESTRICTED_GROUPS.items():
                if user.groups.filter(name=group_name).exists():
                    if not any(
                        self._path_matches(request.path, prefix)
                        for prefix in allowed_prefixes
                    ):
                        return JsonResponse({"detail": "Forbidden"}, status=403)
                    break

        return self.get_response(request)

    @staticmethod
    def _path_matches(path: str, prefix: str) -> bool:
        """Match bare prefix and optional ``/api`` URL prefix."""
        return path.startswith(prefix) or path.startswith(f"/api{prefix}")
