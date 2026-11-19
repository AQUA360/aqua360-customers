from rest_framework.permissions import BasePermission

class RestrictOVUserToOVApp(BasePermission):
    """
    If user is in 'ov' group, they can only access OV app endpoints.
    Other users are unaffected.
    Apps with custom authentication (GOT, lecturapp) are exempt.
    """
    def has_permission(self, request, view):
        # Allow apps with custom authentication to handle their own auth
        exempt_paths = ['/got/', '/lecturapp/']
        for path in exempt_paths:
            if request.path.startswith(path):
                return True
        
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.groups.filter(name="ov").exists():
            # Only allow access if the view is tagged as OV app
            return getattr(view, "app_label", None) == "ov"

        # Non-OV users: let other permission classes decide
        return True


class IsOVUser(BasePermission):
    """Només usuaris del grup «ov» (el frontal de l'Oficina Virtual) i
    superusuaris. Per a les vistes OV noves, que no poden quedar obertes a
    qualsevol usuari autenticat (tiquets 2652 i 2654)."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or user.groups.filter(name="ov").exists()
