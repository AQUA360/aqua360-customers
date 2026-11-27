import re

from rest_framework import permissions
from rest_framework import exceptions

from auth.permissions import DjangoModelViewPermissions
from auth.roles import is_customers_account
from billing.permissions import InvoicePermission
from claimrequest.permissions import ClaimRequestPermission
from contract.permissions import ContractPermission, RelatedModuleReadMixin
from service.permissions import SupplyPointPermission

# Els valors de ConfigProject governen el comportament de tota la instal·lació: els pot
# llegir qualsevol usuari autenticat (les pantalles consulten activadors i tokens d'estats),
# però només els pot modificar qui té `coredata.change_configproject`.
CONFIG_PROJECT_CHANGE_PERM = 'coredata.change_configproject'

# Valors que no es retornen als qui no poden modificar la configuració (claus, contrasenyes...).
# Els tokens `*_token` d'estats i tipus NO hi són: són identificadors de dades, no secrets.
SENSITIVE_CONFIG_PATTERN = re.compile(
    r'(secret|password|passwd|api_?key|private|credential|authentication_token|auth_token|access_token)',
    re.IGNORECASE,
)
MASKED_CONFIG_VALUE = '********'


def can_edit_config_project(user):
    """Si l'usuari pot modificar la configuració del projecte.

    El compte `customers` sempre; la resta, només amb el permís del model donat de manera
    explícita. Cap superusuari ni administrador hi entra pel simple fet de ser-ho (Django els
    donaria tots els permisos): configurar la instal·lació és cosa del compte tècnic.
    """
    if not user or not user.is_authenticated:
        return False
    if is_customers_account(user):
        return True
    if user.is_superuser or user.is_staff:
        return False
    return user.has_perm(CONFIG_PROJECT_CHANGE_PERM)


def is_sensitive_config(token):
    return bool(token and SENSITIVE_CONFIG_PATTERN.search(token))


def visible_config_value(token, value, user):
    """El valor tal com el pot veure `user`: els sensibles, emmascarats si no pot modificar."""
    if value and is_sensitive_config(token) and not can_edit_config_project(user):
        return MASKED_CONFIG_VALUE
    return value


class ConfigProjectPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        """Lectura per a qualsevol usuari autenticat; escriptura només amb el permís de canvi."""
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return can_edit_config_project(request.user)

class MainPermissionPermission(permissions.BasePermission):
    """Catàleg de permisos per rol (MainPermission): el llegeixen les pantalles de
    grups de qualsevol usuari autenticat, però només el pot modificar el
    compte `customers`, com la configuració del projecte."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return is_customers_account(request.user)

class PersonPermission(permissions.BasePermission):
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise exceptions.MethodNotAllowed(request.method)
        
        # OPTIONS (metadades) per a qualsevol usuari autenticat, com DjangoModelPermissions
        if request.method == 'OPTIONS':
            return True

        method_permissions = {
            'GET': 'view_person',
            'HEAD': 'view_person',
            'POST': 'add_person',
            'PUT': 'change_person',
            'PATCH': 'change_person',
            'DELETE': 'delete_person',
        }
        
        required_permission = method_permissions.get(request.method)
        if not required_permission:
            raise exceptions.MethodNotAllowed(request.method)
        
        return request.user.has_perm(f'coredata.{required_permission}')

class PersonReadPermission(RelatedModuleReadMixin, PersonPermission):
    """PersonPermission, i lectura per als usuaris d'un mòdul relacionat."""


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

# Carrers i tipus de via: els fan servir els selectors d'adreça de moltes pantalles
# (persones, contractes, punts de subministrament, comptadors, escomeses, finques, rutes,
# talls, ordres, comunicacions, reclamacions...). Els rols no donen `view_street` (no és
# a cap MainPermission), així que qui pot llegir algun d'aquests mòduls pot llegir els
# carrers; modificar-los demana el permís del model.
ADDRESS_READ_PERMS = (
    'coredata.view_street',
    'coredata.change_street',
    'coredata.view_person',
    'contract.view_contract',
    'contract.view_contractrequest',
    'contract.view_piggybank',
    'service.view_supplypoint',
    'service.view_meter',
    'service.view_connection',
    'service.view_connectionrequest',
    'service.view_property',
    'service.view_route',
    'service.view_supplycut',
    'billing.view_invoice',
    'billing.view_reading',
    'claimrequest.view_claimrequest',
    'order.view_order',
    'communication.view_communication',
    'fraud.view_fraud',
)


class StreetPermission(DjangoModelViewPermissions):
    """Lectura amb el permís del model o d'un mòdul que fa servir adreces; escriptura
    amb add/change/delete del model. `resolve_ids` és un POST que només consulta."""

    read_fallback_perms = ADDRESS_READ_PERMS
    read_only_actions = ('resolve_ids',)


class HolidayPermission(DjangoModelViewPermissions):
    """Festius: els llegeix la configuració d'incidències (càlcul de terminis en dies
    hàbils); modificar-los demana el permís del model."""

    read_fallback_perms = ('notification.view_incident',)
