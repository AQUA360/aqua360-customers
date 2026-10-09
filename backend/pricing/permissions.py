from rest_framework import permissions
from rest_framework import exceptions

class PriceRatePermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_pricerate',
            'POST': 'add_pricerate',
            'PUT': 'change_pricerate',
            'PATCH': 'change_pricerate',
            'DELETE': 'delete_pricerate',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'pricing.{required_permission}')

class ProductPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_product',
            'POST': 'add_product',
            'PUT': 'change_product',
            'PATCH': 'change_product',
            'DELETE': 'delete_product',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'pricing.{required_permission}')
