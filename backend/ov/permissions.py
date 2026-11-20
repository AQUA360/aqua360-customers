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


class IsOVServiceUser(BasePermission):
    """
    Només el compte de servei de l'Oficina Virtual (usuaris del grup `ov`).

    Per a endpoints de l'OV que no ha de poder cridar cap altre usuari
    autenticat del Customers (p. ex. els que, amb només un DNI, retornen
    dades d'una persona). Així la vista té un permís propi i no s'ha
    d'afegir a `customers/view_permissions_baseline.txt`.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return user.groups.filter(name="ov").exists()
