from django.db.models import Q
from rest_framework import permissions
from rest_framework import exceptions

from claimrequest.permissions import ClaimRequestPermission

class OrderPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_order',
            'POST': 'add_order',
            'PUT': 'change_order',
            'PATCH': 'change_order',
            'DELETE': 'delete_order',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'order.{required_permission}')

class OperatorPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_operator',
            'POST': 'add_operator',
            'PUT': 'change_operator',
            'PATCH': 'change_operator',
            'DELETE': 'delete_operator',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'order.{required_permission}')

class ClaimRequestOrderPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        order_permission = OrderPermission().has_permission(request, view)
        claim_request_permission = ClaimRequestPermission().has_permission(request, view)
        
        return order_permission or claim_request_permission


def _parse_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_ids(value):
    ids = [_parse_id(v) for v in (value or '').split(',') if v.strip()]
    return ids if ids and None not in ids else None


# Fitxes d'altres mòduls des de les quals es llisten ordres. Qui no té
# `view_order` pot llegir les ordres d'una fitxa si té permís per veure-la,
# amb el mateix criteri que ClaimRequestOrderPermission.
# (paràmetre del filtre, permís de la fitxa, lector del valor, Q de l'ordre)
RELATED_ORDER_FILTERS = (
    ('contract', 'contract.view_contract', _parse_id,
     lambda v: Q(contract__id=v) | Q(supply_point__contracts__id=v) | Q(supply_point__default_contracts__id=v)),
    ('contract_id', 'contract.view_contract', _parse_id,
     lambda v: Q(contract__id=v) | Q(supply_point__contracts__id=v) | Q(supply_point__default_contracts__id=v)),
    ('contract_request', 'contract.view_contractrequest', _parse_id,
     lambda v: Q(contract_request__id=v)),
    ('contract_termination_request', 'contract.view_contractterminationrequest', _parse_id,
     lambda v: Q(contract_termination_request__id=v)),
    ('connection', 'service.view_connection', _parse_id,
     lambda v: Q(connection__id=v)),
    ('connection_request', 'service.view_connectionrequest', _parse_id,
     lambda v: Q(connection_request__id=v)),
    ('incident', 'notification.view_incident', _parse_id,
     lambda v: Q(incident__id=v)),
    ('supply_point_ids', 'service.view_supplypoint', _parse_ids,
     lambda v: Q(supply_point__id__in=v)),
    ('claim_request', 'claimrequest.view_claimrequest', _parse_id,
     lambda v: Q(claim_request__id=v)),
)

# Relació directa de l'ordre -> permís per veure-la (detall d'una ordre).
RELATED_ORDER_FIELDS = (
    ('contract', 'contract.view_contract'),
    ('contract_request', 'contract.view_contractrequest'),
    ('contract_termination_request', 'contract.view_contractterminationrequest'),
    ('connection', 'service.view_connection'),
    ('connection_request', 'service.view_connectionrequest'),
    ('incident', 'notification.view_incident'),
    ('supply_point', 'service.view_supplypoint'),
    ('claim_request', 'claimrequest.view_claimrequest'),
)


def related_orders_scope(request):
    """Q que limita el llistat a les fitxes filtrades que l'usuari pot veure,
    o None si no n'hi ha cap (paràmetre absent, buit, no vàlid o sense permís)."""
    scope = None
    for param, perm, parse, build_q in RELATED_ORDER_FILTERS:
        value = parse(request.query_params.get(param))
        if value is None or not request.user.has_perm(perm):
            continue
        q = build_q(value)
        scope = q if scope is None else scope & q
    return scope


class OrderReadPermission(permissions.BasePermission):
    """Lectura d'una ordre (per exemple, generar-ne el PDF): sempre `view_order`,
    sigui quin sigui el mètode."""

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.has_perm('order.view_order')
        )


class OrderViewSetPermission(OrderPermission):
    """OrderPermission, i a més deixa llegir sense `view_order` el llistat
    filtrat per una fitxa que l'usuari pot veure i el detall d'una ordre
    lligada a una fitxa que pot veure. La vista ha de limitar el queryset del
    llistat amb `related_orders_scope`."""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        if request.method != 'GET':
            return False
        action = getattr(view, 'action', None)
        if action == 'list':
            return related_orders_scope(request) is not None
        if action == 'retrieve':
            return any(request.user.has_perm(perm) for _, perm in RELATED_ORDER_FIELDS)
        return False

    def has_object_permission(self, request, view, obj):
        if request.user.has_perm('order.view_order') or request.method != 'GET':
            return True
        return any(
            getattr(obj, f'{field}_id') is not None and request.user.has_perm(perm)
            for field, perm in RELATED_ORDER_FIELDS
        )
