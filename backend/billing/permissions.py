from rest_framework import permissions
from rest_framework import exceptions

from claimrequest.permissions import ClaimRequestPermission
from contract.permissions import ContractPermission, ContractRequestPermission
from service.permissions import ConnectionRequestPermission

class InvoicePermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_invoice',
            'POST': 'add_invoice',
            'PUT': 'change_invoice',
            'PATCH': 'change_invoice',
            'DELETE': 'delete_invoice',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'billing.{required_permission}')

class PaymentPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_payment',
            'POST': 'add_payment',
            'PUT': 'change_payment',
            'PATCH': 'change_payment',
            'DELETE': 'delete_payment',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'billing.{required_permission}')

class BillingPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_billing',
            'POST': 'add_billing',
            'PUT': 'change_billing',
            'PATCH': 'change_billing',
            'DELETE': 'delete_billing',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'billing.{required_permission}')

class CommitmentDepositPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_commitmentdeposit',
            'POST': 'add_commitmentdeposit',
            'PUT': 'change_commitmentdeposit',
            'PATCH': 'change_commitmentdeposit',
            'DELETE': 'delete_commitmentdeposit',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'billing.{required_permission}')

class ReadingPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_reading',
            'POST': 'add_reading',
            'PUT': 'change_reading',
            'PATCH': 'change_reading',
            'DELETE': 'delete_reading',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'billing.{required_permission}')

class ReadingBatchPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_readingbatch',
            'POST': 'add_readingbatch',
            'PUT': 'change_readingbatch',
            'PATCH': 'change_readingbatch',
            'DELETE': 'delete_readingbatch',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'billing.{required_permission}')

class GeneralPaymentPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        contract_permission = ContractPermission().has_permission(request, view)
        contractrequest_permission = ContractRequestPermission().has_permission(request, view)
        connectionrequest_permission = ConnectionRequestPermission().has_permission(request, view)
        invoice_permission = InvoicePermission().has_permission(request, view)
        claim_request_permission = ClaimRequestPermission().has_permission(request, view)
        
        return contract_permission or contractrequest_permission or connectionrequest_permission or invoice_permission or claim_request_permission
        