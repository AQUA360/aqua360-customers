from rest_framework import permissions
from rest_framework import exceptions

class CommunicationPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_communication',
            'POST': 'add_communication',
            'PUT': 'change_communication',
            'PATCH': 'change_communication',
            'DELETE': 'delete_communication',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'communication.{required_permission}')