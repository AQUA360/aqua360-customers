from django.contrib import admin
from .models import ConfigProject,Address, Street, StreetType, Person, City, Province, PostalCode, PersonBank, PersonAddress, PersonCNAE, Bank, PersonContact, Country, CNAE, StreetNumber, CallRegister, IdentificationType
        
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