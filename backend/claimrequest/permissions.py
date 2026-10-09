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
