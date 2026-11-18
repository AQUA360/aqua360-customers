from rest_framework import permissions
from rest_framework import exceptions

class ContractPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        # OPTIONS (metadades) per a qualsevol usuari autenticat, com DjangoModelPermissions
        if request.method == 'OPTIONS':
            return True

        method_permissions = {
            'GET': 'view_contract',
            'HEAD': 'view_contract',
            'POST': 'add_contract',
            'PUT': 'change_contract',
            'PATCH': 'change_contract',
            'DELETE': 'delete_contract',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'contract.{required_permission}')

class ContractRequestPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        # OPTIONS (metadades) per a qualsevol usuari autenticat, com DjangoModelPermissions
        if request.method == 'OPTIONS':
            return True

        method_permissions = {
            'GET': 'view_contractrequest',
            'HEAD': 'view_contractrequest',
            'POST': 'add_contractrequest',
            'PUT': 'change_contractrequest',
            'PATCH': 'change_contractrequest',
            'DELETE': 'delete_contractrequest',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'contract.{required_permission}')
    

class ContractTerminationRequestPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        # OPTIONS (metadades) per a qualsevol usuari autenticat, com DjangoModelPermissions
        if request.method == 'OPTIONS':
            return True

        method_permissions = {
            'GET': 'view_contractterminationrequest',
            'HEAD': 'view_contractterminationrequest',
            'POST': 'add_contractterminationrequest',
            'PUT': 'change_contractterminationrequest',
            'PATCH': 'change_contractterminationrequest',
            'DELETE': 'delete_contractterminationrequest',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'contract.{required_permission}')

class BailPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        # OPTIONS (metadades) per a qualsevol usuari autenticat, com DjangoModelPermissions
        if request.method == 'OPTIONS':
            return True

        method_permissions = {
            'GET': 'view_bail',
            'HEAD': 'view_bail',
            'POST': 'add_bail',
            'PUT': 'change_bail',
            'PATCH': 'change_bail',
            'DELETE': 'delete_bail',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'contract.{required_permission}')


# Pantalles d'altres mòduls (factures, lectures, ordres, punts de subministrament,
# comunicacions, guardioles) consulten el contracte, la sol·licitud o la persona
# de la fitxa que mostren. Qui pot llegir algun d'aquests mòduls també pot
# llegir les fitxes de contractació, però no modificar-les.
RELATED_MODULE_READ_PERMS = (
    'billing.view_invoice',
    'billing.view_reading',
    'order.view_order',
    'service.view_supplypoint',
    'communication.view_communication',
    'contract.view_piggybank',
)


def can_read_from_related_module(user):
    """Si l'usuari pot llegir algun mòdul que consulta les fitxes de contractació."""
    return any(user.has_perm(perm) for perm in RELATED_MODULE_READ_PERMS)


class RelatedModuleReadMixin:
    """Afegeix la lectura (GET/HEAD) per als usuaris d'un mòdul relacionat."""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        return request.method in ('GET', 'HEAD') and can_read_from_related_module(request.user)


class ContractReadPermission(RelatedModuleReadMixin, ContractPermission):
    pass


class ContractRequestReadPermission(RelatedModuleReadMixin, ContractRequestPermission):
    pass


class ContractPdfPermission(permissions.BasePermission):
    """PDF d'un contracte (`is_contract=true`) o d'una sol·licitud de contracte:
    cal poder veure el que es descarrega."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        is_contract = request.query_params.get('is_contract', 'false').lower() == 'true'
        perm = 'contract.view_contract' if is_contract else 'contract.view_contractrequest'
        return request.user.has_perm(perm) or can_read_from_related_module(request.user)
