from rest_framework import permissions


def export_permission_class(app_label, model_name):
    """
    Permission class per a accions d'exportació: exigeix `view_<model_name>`
    encara que la petició sigui un POST (DjangoModelPermissions exigiria
    `add_<model_name>` en un POST, permís equivocat per a una acció de
    només lectura com exportar).
    """
    class _ExportPermission(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            return request.user.has_perm(f'{app_label}.view_{model_name}')

    _ExportPermission.__name__ = f'Export{model_name.capitalize()}Permission'
    return _ExportPermission
