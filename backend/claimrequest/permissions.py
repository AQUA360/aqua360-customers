from rest_framework import permissions
from rest_framework import exceptions

class ClaimRequestPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_claimrequest',
            'POST': 'add_claimrequest',
            'PUT': 'change_claimrequest',
            'PATCH': 'change_claimrequest',
            'DELETE': 'delete_claimrequest',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'claimrequest.{required_permission}')

class VulnerabilityRequestPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_vulnerabilityrequest',
            'POST': 'add_vulnerabilityrequest',
            'PUT': 'change_vulnerabilityrequest',
            'PATCH': 'change_vulnerabilityrequest',
            'DELETE': 'delete_vulnerabilityrequest',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'claimrequest.{required_permission}')


# --- Vistes de reclamacions sense permís propi (tiquet 2688) -------------------------------

from auth.permissions import DjangoModelViewPermissions  # noqa: E402


def _requires(name, *required, all_required=False):
    class _Requires(permissions.BasePermission):
        required_permissions = required

        def has_permission(self, request, view):
            user = request.user
            if not user or not user.is_authenticated:
                return False
            if request.method == 'OPTIONS':
                return True
            check = all if all_required else any
            return check(user.has_perm(permission) for permission in self.required_permissions)

    _Requires.__name__ = _Requires.__qualname__ = name
    return _Requires


# Cerca de dades d'una reclamació (és una tasca, però només consulta) i resultat
CanViewClaimRequestData = _requires('CanViewClaimRequestData', 'claimrequest.view_claimrequest')
# Accions que modifiquen una reclamació sense ser un PUT/PATCH del model
CanChangeClaimRequest = _requires('CanChangeClaimRequest', 'claimrequest.change_claimrequest')
# Altes massives de vulnerabilitat: canvien l'estat de moltes sol·licituds
CanChangeVulnerabilityRequests = _requires(
    'CanChangeVulnerabilityRequests', 'claimrequest.change_vulnerabilityrequest'
)
# Baixes massives de contractes: acaben en un tall de servei, difícil de revertir
CanTerminateContracts = _requires(
    'CanTerminateContracts', 'contract.add_contractterminationrequest', 'claimrequest.view_claimrequest',
    all_required=True,
)


class ClaimRequestModelPermission(DjangoModelViewPermissions):
    """Reclamacions i els seus passos: les pantalles de contractes també les consulten."""

    read_fallback_perms = ('contract.view_contract', 'contract.view_contractrequest')


class VulnerabilityModelPermission(DjangoModelViewPermissions):
    """Sol·licituds de vulnerabilitat i els seus tipus: es veuen des de contractes i reclamacions."""

    read_fallback_perms = (
        'contract.view_contract', 'contract.view_contractrequest', 'claimrequest.view_claimrequest',
    )
