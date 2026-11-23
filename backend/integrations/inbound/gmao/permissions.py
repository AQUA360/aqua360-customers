from rest_framework.permissions import BasePermission

# Grup dels usuaris tècnics de la integració amb el GMAO
GMAO_GROUP = "gmao"


class IsGMAOUser(BasePermission):
    """Només usuaris autenticats del grup `gmao`."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.groups.filter(name=GMAO_GROUP).exists()
        )
