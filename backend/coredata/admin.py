from django.contrib import admin
from .models import ConfigProject,Address, Street, StreetType, Person, City, Province, PostalCode, PersonBank, PersonAddress, PersonCNAE, Bank, PersonContact, Country, CNAE, StreetNumber, CallRegister, IdentificationType, Holiday, DeployRecord
        
@admin.register(ConfigProject)
class ConfigProjectAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'value', 'file')

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'iso_code')

@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name',)

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'province')

@admin.register(PostalCode)
class PostalCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'code')

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'street','street_number')

@admin.register(Street)
class StreetAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    
@admin.register(StreetType)
class StreetTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'abbreviation', 'name')
        
@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'surname', 'token','is_juridic')

@admin.register(PersonBank)
class PersonBankAdmin(admin.ModelAdmin):
    list_display = ('id','token', 'iban', 'country', 'role')

@admin.register(PersonAddress)
class PersonAddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'person', 'address', 'attention_to', 'is_billing')

@admin.register(PersonCNAE)
class PersonCNAEAdmin(admin.ModelAdmin):
    list_display = ('id', 'person', 'cnae')

@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'bic', 'active')
    search_fields = ('token', 'name')
    
@admin.register(PersonContact)
class PersonContactAdmin(admin.ModelAdmin):
    list_display = ('id', 'phone', 'email', 'is_active')

    
@admin.register(CNAE)
class CNAEAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'description')

@admin.register(StreetNumber)
class StreetNumberAdmin(admin.ModelAdmin):
    list_display = ('id', 'number_type')

@admin.register(CallRegister)
class CallRegisterAdmin(admin.ModelAdmin):
    list_display = ('id', 'token')

@admin.register(IdentificationType)
class IdentificationTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'is_default')
@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'name', 'exploitation')


@admin.register(DeployRecord)
class DeployRecordAdmin(admin.ModelAdmin):
    list_display = ('deployed_at', 'component', 'release', 'commit', 'branch', 'built_at')
    list_filter = ('component',)
    search_fields = ('release', 'commit')


# --- Tokens d'accés: mostren quan caduquen ---------------------------------
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authtoken.admin import TokenAdmin as DRFTokenAdmin
from rest_framework.authtoken.models import TokenProxy

from coredata.authentication import is_integration_user
from coredata.models import AuthSessionToken


@admin.register(AuthSessionToken)
class AuthSessionTokenAdmin(admin.ModelAdmin):
    """Tokens de sessió de les persones. Caduquen per inactivitat o per antiguitat."""
    list_display = ('user', 'created', 'last_used', 'expires_at', 'is_expired')
    search_fields = ('user__username', 'user__email')
    ordering = ('-created',)
    raw_id_fields = ('user',)
    readonly_fields = ('key', 'created', 'last_used', 'expires_at', 'is_expired')
    fields = ('user', 'key', 'created', 'last_used', 'expires_at', 'is_expired')

    @admin.display(description='Caduca')
    def expires_at(self, obj):
        # El primer límit que s'arribi: antiguitat màxima o inactivitat des de l'últim ús.
        return min(
            obj.created + timedelta(days=settings.AUTH_TOKEN_MAX_AGE_DAYS),
            obj.last_used + timedelta(hours=settings.AUTH_TOKEN_IDLE_HOURS),
        )

    @admin.display(description='Caducat', boolean=True)
    def is_expired(self, obj):
        return obj.is_expired()


admin.site.unregister(TokenProxy)


@admin.register(TokenProxy)
class TokenAdmin(DRFTokenAdmin):
    """Tokens de DRF: només serveixen per als usuaris d'integració i caduquen."""
    list_display = ('key', 'user', 'created', 'expires_at', 'is_expired', 'is_integration')

    @admin.display(description='Caduca')
    def expires_at(self, obj):
        if not is_integration_user(obj.user):
            return None
        return obj.created + timedelta(days=settings.AUTH_INTEGRATION_TOKEN_MAX_AGE_DAYS)

    @admin.display(description='Caducat', boolean=True)
    def is_expired(self, obj):
        expires_at = self.expires_at(obj)
        # Un token de DRF d'una persona no s'accepta mai: compta com a caducat.
        return True if expires_at is None else expires_at <= timezone.now()

    @admin.display(description='Integració', boolean=True)
    def is_integration(self, obj):
        return is_integration_user(obj.user)
