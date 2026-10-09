from django.contrib import admin

from .models import *

admin.site.register(FraudStatus)
class FraudStatusAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'position', 'is_default')
    search_fields = ('name', 'color')
    list_filter = ('is_default',)

admin.site.register(Fraud)
class FraudAdmin(admin.ModelAdmin):
    list_display = ('token', 'detection_date', 'status', 'supply_point', 'contract', 'is_active')
    search_fields = ('token', 'detection_date', 'status', 'supply_point', 'contract')
    list_filter = ('status', 'is_active')

admin.site.register(FraudDocumentation)
class FraudDocumentationAdmin(admin.ModelAdmin):
    list_display = ('name', 'file')
    search_fields = ('name',)
    list_filter = ('name',)

admin.site.register(FraudObservation)
class FraudObservationAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'updated_at', 'observation', 'status', 'status_name', 'is_active', 'user')
    search_fields = ('observation', 'status', 'status_name')
    list_filter = ('is_active', 'user')

admin.site.register(FraudReport)
class FraudReportAdmin(admin.ModelAdmin):
    list_display = ('token', 'detection_date', 'status', 'supply_point', 'contract', 'is_active')
    search_fields = ('token', 'detection_date', 'status', 'supply_point', 'contract')
    list_filter = ('status', 'is_active')

admin.site.register(FraudImage)
class FraudImageAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'updated_at', 'fraud_report', 'image')
    search_fields = ('fraud_report', 'image')
    list_filter = ('fraud_report',)