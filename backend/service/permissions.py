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