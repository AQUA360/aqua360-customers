from rest_framework import permissions
from rest_framework import exceptions

from billing.permissions import InvoicePermission
from claimrequest.permissions import ClaimRequestPermission
from contract.permissions import ContractPermission
from service.permissions import SupplyPointPermission

class PersonPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        method_permissions = {
            'GET': 'view_person',
            'POST': 'add_person',
            'PUT': 'change_person',
            'PATCH': 'change_person',
            'DELETE': 'delete_person',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'coredata.{required_permission}')

class AddressPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Native Street permissions
        if request.user.has_perm('coredata.view_street') or request.user.has_perm('coredata.change_street'):
            return True

        # Fallback to other address-related modules
        try:
            person_permission = PersonPermission().has_permission(request, view)
        except Exception:
            person_permission = False
            
        try:
            contract_permission = ContractPermission().has_permission(request, view)
        except Exception:
            contract_permission = False
            
        try:
            supply_point_permission = SupplyPointPermission().has_permission(request, view)
        except Exception:
            supply_point_permission = False
            
        try:
            invoice_permission = InvoicePermission().has_permission(request, view)
        except Exception:
            invoice_permission = False
            
        try:
            claim_request_permission = ClaimRequestPermission().has_permission(request, view)
        except Exception:
            claim_request_permission = False
        
        return person_permission or contract_permission or supply_point_permission or invoice_permission or claim_request_permission