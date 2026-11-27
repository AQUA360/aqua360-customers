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
        

# --- Vistes de facturació sense permís propi (tiquet 2687) ---------------------------------
#
# Les vistes que consulten o generen documents no són d'un sol model: demanen qualsevol dels
# permisos de la llista (un mòdul relacionat, com els contractes, pot necessitar-ne la lectura).
# OPTIONS (metadades) continua obert als usuaris autenticats, com a DjangoModelPermissions.

from auth.permissions import DjangoModelViewPermissions  # noqa: E402


def _any_permission(name, *required):
    class _AnyPermission(permissions.BasePermission):
        required_permissions = required

        def has_permission(self, request, view):
            user = request.user
            if not user or not user.is_authenticated:
                return False
            if request.method == 'OPTIONS':
                return True
            return any(user.has_perm(permission) for permission in self.required_permissions)

    _AnyPermission.__name__ = _AnyPermission.__qualname__ = name
    return _AnyPermission


# Cua i estat dels processos de facturació
CanViewBillingProcess = _any_permission('CanViewBillingProcess', 'billing.view_billing')
CanChangeBillingProcess = _any_permission('CanChangeBillingProcess', 'billing.change_billing')

# Documents i exportacions
CanViewInvoiceDocuments = _any_permission('CanViewInvoiceDocuments', 'billing.view_invoice')
CanViewPaymentDocuments = _any_permission('CanViewPaymentDocuments', 'billing.view_payment')
CanViewInvoiceOrPaymentDocuments = _any_permission(
    'CanViewInvoiceOrPaymentDocuments', 'billing.view_invoice', 'billing.view_payment'
)
CanViewSepaDocuments = _any_permission(
    'CanViewSepaDocuments',
    'billing.view_payment', 'contract.view_contract', 'contract.view_contractrequest',
)
CanViewReadingExports = _any_permission('CanViewReadingExports', 'billing.view_reading')
CanViewContractEstimation = _any_permission(
    'CanViewContractEstimation', 'contract.view_contract', 'billing.view_invoice'
)

# Enviament de correus de factures i mandats: modifiquen l'estat (creen comunicacions)
CanSendInvoiceEmails = _any_permission('CanSendInvoiceEmails', 'billing.change_invoice')
CanSendPaymentEmails = _any_permission('CanSendPaymentEmails', 'billing.change_payment')

# Pantalles d'altres mòduls que consulten aquests models
_CONTRACT_SCREENS = ('contract.view_contract', 'contract.view_contractrequest', 'claimrequest.view_claimrequest')


class InvoiceModelPermission(DjangoModelViewPermissions):
    """Factures: veure demana `view_invoice`; les pantalles de contractes i reclamacions també les llegeixen."""

    read_fallback_perms = _CONTRACT_SCREENS + ('communication.view_communication',)


class PaymentModelPermission(DjangoModelViewPermissions):
    read_fallback_perms = _CONTRACT_SCREENS + ('billing.view_invoice', 'communication.view_communication')


class PaymentTypeModelPermission(DjangoModelViewPermissions):
    """Tipus de pagament: catàleg que fan servir els selectors de contractes, factures i cobraments."""

    read_fallback_perms = _CONTRACT_SCREENS + ('billing.view_invoice', 'billing.view_payment')


class ReadingModelPermission(DjangoModelViewPermissions):
    read_fallback_perms = (
        'service.view_supplypoint', 'service.view_meter', 'service.view_route',
        'contract.view_contract', 'notification.view_incident',
    )


class BillingModelPermission(DjangoModelViewPermissions):
    pass


class SepaConceptConfigPermission(permissions.BasePermission):
    """Concepte dels rebuts SEPA (ConfigProject): llegir-lo demana veure pagaments; canviar-lo,
    poder modificar la configuració del projecte."""

    def has_permission(self, request, view):
        from coredata.permissions import can_edit_config_project

        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return request.method == 'OPTIONS' or user.has_perm('billing.view_payment') or can_edit_config_project(user)
        return can_edit_config_project(user)


class SmartMeteringSettingsPermission(permissions.BasePermission):
    """Configuració de Smart Metering: la veu qui pot veure les tandes de lectures o modificar la
    configuració del projecte. El token d'autenticació només el veu qui la pot modificar."""

    def has_permission(self, request, view):
        from coredata.permissions import can_edit_config_project

        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method == 'OPTIONS':
            return True
        return can_edit_config_project(user) or user.has_perm('billing.view_readingbatch')
