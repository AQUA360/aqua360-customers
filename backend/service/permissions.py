from rest_framework import permissions
from rest_framework import exceptions

class SupplyPointPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_supplypoint',
            'POST': 'add_supplypoint',
            'PUT': 'change_supplypoint',
            'PATCH': 'change_supplypoint',
            'DELETE': 'delete_supplypoint',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class MeterPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_meter',
            'POST': 'add_meter',
            'PUT': 'change_meter',
            'PATCH': 'change_meter',
            'DELETE': 'delete_meter',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class ConnectionPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_connection',
            'POST': 'add_connection',
            'PUT': 'change_connection',
            'PATCH': 'change_connection',
            'DELETE': 'delete_connection',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class PropertyPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_property',
            'POST': 'add_property',
            'PUT': 'change_property',
            'PATCH': 'change_property',
            'DELETE': 'delete_property',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class RoutePermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_route',
            'POST': 'add_route',
            'PUT': 'change_route',
            'PATCH': 'change_route',
            'DELETE': 'delete_route',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class ClusterPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_cluster',
            'POST': 'add_cluster',
            'PUT': 'change_cluster',
            'PATCH': 'change_cluster',
            'DELETE': 'delete_cluster',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class ConnectionRequestPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_connectionrequest',
            'POST': 'add_connectionrequest',
            'PUT': 'change_connectionrequest',
            'PATCH': 'change_connectionrequest',
            'DELETE': 'delete_connectionrequest',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class SupplyCutPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_supplycut',
            'POST': 'add_supplycut',
            'PUT': 'change_supplycut',
            'PATCH': 'change_supplycut',
            'DELETE': 'delete_supplycut',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class CompanyPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_company',
            'POST': 'add_company',
            'PUT': 'change_company',
            'PATCH': 'change_company',
            'DELETE': 'delete_company',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

class ExploitationPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_exploitation',
            'POST': 'add_exploitation',
            'PUT': 'change_exploitation',
            'PATCH': 'change_exploitation',
            'DELETE': 'delete_exploitation',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'service.{required_permission}')

# --- Vistes de service sense permís de lectura propi (tiquet 2703) -------------------------

from auth.permissions import DjangoModelViewPermissions  # noqa: E402

# Pantalles d'altres mòduls que consulten punts de subministrament, comptadors, finques,
# connexions, rutes, empreses i explotacions. Només donen lectura, mai escriptura.
SERVICE_READ_FALLBACK_PERMS = (
    'contract.view_contract',
    'contract.view_contractrequest',
    'order.view_order',
    'fraud.view_fraud',
    'billing.view_invoice',
    'billing.view_payment',
    'billing.view_reading',
    'claimrequest.view_claimrequest',
    'lecturapp.view_readingoperator',
)


class ServiceModelPermission(DjangoModelViewPermissions):
    """Vistes de service: lectura amb `view_<model>` (o des de pantalles d'altres mòduls).

    - `read_only_actions`: POST que només consulten o encuen una exportació (demanen lectura).
    - `change_actions`: POST que modifiquen un objecte que ja existeix; DjangoModelPermissions
      hi demanaria `add_<model>`, i amb només el permís d'afegir es podria modificar.
    """

    read_fallback_perms = SERVICE_READ_FALLBACK_PERMS
    change_actions = ()

    def has_permission(self, request, view):
        if getattr(view, 'action', None) in self.change_actions and request.method == 'POST':
            user = request.user
            if not user or not user.is_authenticated:
                return False
            model = self._queryset(view).model
            return user.has_perm(f'{model._meta.app_label}.change_{model._meta.model_name}')
        return super().has_permission(request, view)


class ConnectionModelPermission(ServiceModelPermission):
    change_actions = ('activate',)


class SupplyCutModelPermission(ServiceModelPermission):
    change_actions = ('resolve_review', 'remove_supply_point', 'start_cut', 'finish_cut')


class RouteModelPermission(ServiceModelPermission):
    read_only_actions = ('export_positions', 'export_supply_points')


class MeterModelPermission(ServiceModelPermission):
    read_only_actions = ('get_by_reading_document',)


def requires_any_permission(name, *required):
    """Permís que demana tenir almenys un dels permisos indicats (`app.codename`)."""

    class _RequiresAny(permissions.BasePermission):
        required_permissions = required

        def has_permission(self, request, view):
            user = request.user
            return bool(
                user and user.is_authenticated
                and any(user.has_perm(permission) for permission in self.required_permissions)
            )

    _RequiresAny.__name__ = _RequiresAny.__qualname__ = name
    return _RequiresAny


CanChangeMeter = requires_any_permission('CanChangeMeter', 'service.change_meter')
CanChangeRoute = requires_any_permission('CanChangeRoute', 'service.change_route')
CanChangeSupplyPoint = requires_any_permission('CanChangeSupplyPoint', 'service.change_supplypoint')
# Canviar el comptador d'un punt també ho fan les pantalles de contractes, sol·licituds i fraus
CanChangeSupplyPointMeter = requires_any_permission(
    'CanChangeSupplyPointMeter', 'service.change_supplypoint', 'contract.change_contract',
    'contract.change_contractrequest', 'fraud.change_fraud',
)
CanBulkPlanSupplyCuts = requires_any_permission(
    'CanBulkPlanSupplyCuts', 'service.add_supplycut', 'service.change_supplycut',
)
CanAddSupplyCut = requires_any_permission('CanAddSupplyCut', 'service.add_supplycut')
CanViewMeter = requires_any_permission('CanViewMeter', 'service.view_meter')
