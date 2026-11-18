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


def can_read(user, perm):
    """Si l'usuari té el permís de lectura `perm` o el pot llegir per un mòdul relacionat."""
    return user.has_perm(perm) or can_read_from_related_module(user)


class RelatedModuleReadMixin:
    """Afegeix la lectura (GET/HEAD) per als usuaris d'un mòdul relacionat.
    En un ViewSet només val per a les accions de `related_read_actions` (llistat
    i detall): la resta (historial, exportacions...) demanen el permís del model."""

    related_read_actions = ('list', 'retrieve')

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        if request.method not in ('GET', 'HEAD'):
            return False
        action = getattr(view, 'action', None)
        if action is not None and action not in self.related_read_actions:
            return False
        return can_read_from_related_module(request.user)


def required_permission_class(perm, related_read=False):
    """Permís fix per a una vista o acció que no encaixa amb el mètode HTTP: un POST
    que modifica registres existents (`change_*`) o que només consulta (`view_*`).
    Amb `related_read`, també hi accedeixen els usuaris d'un mòdul relacionat."""

    class _RequiredPermission(permissions.BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            if request.method == 'OPTIONS':
                return True
            if related_read:
                return can_read(request.user, perm)
            return request.user.has_perm(perm)

    _RequiredPermission.__name__ = f"Required{perm.split('.')[-1].title().replace('_', '')}Permission"
    return _RequiredPermission


class ContractReadPermission(RelatedModuleReadMixin, ContractPermission):
    # `minimal`: dades bàsiques del contracte per a les comunicacions.
    related_read_actions = ('list', 'retrieve', 'get_minimal')


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
        # Si la sol·licitud ja té contracte, la vista en genera el del contracte:
        # la vista ho torna a comprovar amb `can_read(user, 'contract.view_contract')`.
        return can_read(request.user, perm)
