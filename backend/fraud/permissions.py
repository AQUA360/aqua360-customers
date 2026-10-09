from rest_framework import permissions
from rest_framework import exceptions

class FraudPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_fraud',
            'POST': 'add_fraud',
            'PUT': 'change_fraud',
            'PATCH': 'change_fraud',
            'DELETE': 'delete_fraud',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'fraud.{required_permission}')
