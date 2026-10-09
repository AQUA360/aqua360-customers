from django.contrib import admin

from .models import ContractConsumption, GeneralReport, AccountingCode, AccountingValue, BillingConsumption, AvailableReport

@admin.register(BillingConsumption)
class BillingConsumptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'contract', 'year', 'month', 'total_amount', 'consumption')
    list_filter = ('year', 'month')
    search_fields = ('invoice__token', 'contract__token')

@admin.register(ContractConsumption)
class ContractConsumptionAdmin(admin.ModelAdmin):
    list_display = ('id','contract', 'consumption', 'period')
    # list_filter = ('entity', 'field', 'entity_id', 'service')
    # search_fields = ('contract__token')

@admin.register(GeneralReport)
class GeneralReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'start_date', 'end_date')

@admin.register(AccountingCode)
class AccountingCodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'position')

@admin.register(AccountingValue)
class AccountingValueAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'code')

@admin.register(AvailableReport)
class AvailableReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'section', 'function_name', 'is_active', 'position')
    list_filter = ('section', 'is_active', 'has_custom_config')
    search_fields = ('name', 'function_name', 'description')
    ordering = ('section__position', 'position', 'name')