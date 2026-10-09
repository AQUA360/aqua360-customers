from django.contrib import admin
from .models import BailStatus, Contract, ContractRequest, PaymentType, PiggyBank, PiggyBankMovement, Variable, Bonification, Bail, BailType, ContractObservation, ContractStatus, ContractRequestObservation, BonificationType, BonificationTypeDocumentationType, ContractRequestStatus, ContractUseType, ContractClientType, ContractCategory, ContractRequestType, ContractRepresentative, ContractRepresentativeType, VariableType, ContractRequestDocumentationType, ContractPayment, ContractSurrogation, ContractTerminationRequest, ContractSurrogationType, ContractTerminationType, ContractTerminationStatus, ClauseTemplate, ContractClause, ContractRequestRepresentative, ContractPriceRate, ContractRequestDocumentation, GeneralInvoice

@admin.register(ContractPriceRate)
class ContractPriceRateAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'supply_point', 'price_rate', 'is_active')
    list_filter = ('created_at', 'updated_at', 'supply_point', 'price_rate')
    search_fields = ('token',)

@admin.register(Bail)
class BailAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
    
@admin.register(ContractPayment)
class ContractPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'IBAN', 'type', 'is_active')
    list_filter = ('created_at', 'updated_at', 'type')
    search_fields = ('token', 'IBAN')

@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'status', 'use_type', 'client_type', 'category', 'is_active')
    list_filter = ('created_at', 'updated_at', 'status', 'use_type', 'client_type', 'category')
    search_fields = ('token',)


@admin.register(ContractClause)
class ContractClausesAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'contract','contract_request', 'title', 'is_active')
    list_filter = ('created_at', 'updated_at', 'title')
    search_fields = ('token', 'title')

@admin.register(ContractRepresentative)
class ContractRepresentativeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'contract', 'person', 'is_active')
    list_filter = ('created_at', 'updated_at', 'contract', 'person',)    
    search_fields = ('token', )

@admin.register(ContractRequestRepresentative)
class ContractRequestRepresentativeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'contract_request', 'person', 'is_active')
    list_filter = ('created_at', 'updated_at', 'contract_request', 'person',)    
    search_fields = ('token', )
 
@admin.register(ContractRequest)
class ContractRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'status', 'requested_at', 'approved_at', 'is_active')
    list_filter = ('created_at', 'updated_at', 'status', 'requested_at', 'approved_at')
    search_fields = ('token',)

@admin.register(ClauseTemplate)
class ClauseTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'title', 'is_active')
    list_filter = ('created_at', 'updated_at', 'title')
    search_fields = ('token', 'title')  

@admin.register(Variable)
class VariablesAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(Bonification)
class BonificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at','requested_at', 'approved_at', 'is_active')
    list_filter = ('created_at', 'updated_at', 'requested_at', 'approved_at')
    search_fields = ('token',)

@admin.register(ContractSurrogation)
class ContractSurrogationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'contract', 'type', 'requested_at', 'approved_at', 'is_active')
    list_filter = ('created_at', 'updated_at', 'type', 'contract')
    search_fields = ('token',)
    
@admin.register(ContractTerminationRequest)
class ContractTerminationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'contract', 'type', 'status', 'requested_at', 'approved_at', 'is_active')
    list_filter = ('created_at', 'updated_at', 'type', 'status', 'contract')
    search_fields = ('token',)

@admin.register(BonificationType)
class BonificationTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'is_active')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)


#test

@admin.register(BailType)
class BailTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'position')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
    
@admin.register(BailStatus)
class BailStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'color', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(ContractRequestStatus)
class ContractRequestStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'color', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)


@admin.register(ContractObservation)
class ContractObservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'contract', 'observation', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('contract', 'observation')

@admin.register(ContractStatus)
class ContractStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'color', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
    
@admin.register(ContractRequestObservation)
class ContractRequestObservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'contract_request', 'observation', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('contract_request', 'observation')


@admin.register(BonificationTypeDocumentationType)
class BonificationTypeDocumentationTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'position', 'is_mandatory', 'is_default', 'is_active')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(ContractUseType)
class ContractUseTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(ContractClientType)
class ContractClientTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(ContractCategory)
class ContractCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(ContractRequestType)
class ContractRequestTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'is_active', 'exploitation')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
    
    
@admin.register(ContractRepresentativeType)
class ContractRepresentativeTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'color', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(VariableType)
class VariableTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'data_type', 'position')
    list_filter = ('created_at', 'updated_at', 'data_type')
    search_fields = ('token',)
    
@admin.register(ContractRequestDocumentationType)
class ContractRequestDocumentationTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'list_name', 'position', 'is_mandatory', 'is_active', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
    
@admin.register(ContractRequestDocumentation)
class ContractRequestDocumentationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)


    
@admin.register(PaymentType)
class PaymentTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'name', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at', 'name')
    search_fields = ('token', 'position', 'name')
    


@admin.register(ContractSurrogationType)
class ContractSurrogationTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'name', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at', 'name')
    search_fields = ('token', 'position', 'name')

@admin.register(ContractTerminationType)
class ContractTerminationTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'name', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at', 'name')
    search_fields = ('token', 'position', 'name')

@admin.register(ContractTerminationStatus)
class ContractTerminationStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'token', 'name', 'color', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at', 'name')
    search_fields = ('token', 'position', 'name')

@admin.register(PiggyBank)
class PiggyBankAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'amount', 'is_active')
    list_filter = ('created_at', 'updated_at', 'amount')
    search_fields = ('token',)

@admin.register(PiggyBankMovement)
class PiggyBankMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'amount', 'is_active')
    list_filter = ('created_at', 'updated_at', 'amount')
    search_fields = ('token',)

@admin.register(GeneralInvoice)
class GeneralInvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
