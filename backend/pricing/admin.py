from django.contrib import admin
from .models import PriceRate, Product, Publication, BillingRange, PriceInterval, Adjustment, LineItemType, PriceIntervalStretch, Tax, AdjustmentIntervalStretch, PriceVariableInterval, PriceVariableIntervalStretch, ProductOrigin, VariableCalculation, AdjustmentCondition


@admin.register(PriceVariableInterval)
class PriceVariableIntervalAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token',)

@admin.register(PriceVariableIntervalStretch)
class PriceVariableIntervalStretchAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'stretch', 'end_stretch', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token',)

@admin.register(ProductOrigin)
class ProductOriginAdmin(admin.ModelAdmin):
    list_display = ('id', 'token')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(PriceRate)
class PriceRateAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name',  'is_active', 'origin','position')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token',)
    ordering = ('origin', 'position')

@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'boe_number', 'boe_date', 'reference', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token', 'name', 'boe_number', 'reference', 'content')

@admin.register(BillingRange)
class BillingRangeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'start', 'end', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token', 'name')

@admin.register(PriceInterval)
class PriceIntervalAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'units', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token',)
    
@admin.register(PriceIntervalStretch)
class PriceIntervalStretchAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'price_interval', 'price', 'proportional_price', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token',)

@admin.register(Adjustment)
class AdjustmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'operation',  'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token',)
    
@admin.register(AdjustmentIntervalStretch)
class AdjustmentIntervalStretchAdmin(admin.ModelAdmin):
    list_display = ('id', 'token')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(LineItemType)
class LineItemTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'price', 'proportional_price', 'price_interval', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token', "name")

@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'percent', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('token',)

@admin.register(VariableCalculation)
class VariableCalculationAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
    
@admin.register(AdjustmentCondition)
class AdjustmentConditionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'quantity', 'operation', 'formula')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
