from rest_framework import permissions
from rest_framework import exceptions

class ContractPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_contract',
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
        
        method_permissions = {
            'GET': 'view_contractrequest',
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
        
        method_permissions = {
            'GET': 'view_contractterminationrequest',
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
        
        method_permissions = {
            'GET': 'view_bail',
            'POST': 'add_bail',
            'PUT': 'change_bail',
            'PATCH': 'change_bail',
            'DELETE': 'delete_bail',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'contract.{required_permission}')
