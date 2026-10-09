from rest_framework import permissions
from rest_framework import exceptions

class IncidentPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_incident',
            'POST': 'add_incident',
            'PUT': 'change_incident',
            'PATCH': 'change_incident',
            'DELETE': 'delete_incident',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'notification.{required_permission}')

class NotificationPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_notification',
            'POST': 'add_notification',
            'PUT': 'change_notification',
            'PATCH': 'change_notification',
            'DELETE': 'delete_notification',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'notification.{required_permission}')