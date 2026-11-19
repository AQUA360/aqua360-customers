from rest_framework import permissions


class VerifactuPermission(permissions.BasePermission):
    """Registres de Verifactu: es governen amb els permisos de factura, com
    l'acció `permissions` que fa servir el frontend. Llegir requereix
    `view_invoice` i notificar una factura, `change_invoice`."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method == 'OPTIONS':
            return True
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('billing.view_invoice')
        return request.user.has_perm('billing.change_invoice')
