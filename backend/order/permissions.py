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