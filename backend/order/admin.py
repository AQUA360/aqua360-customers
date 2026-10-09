from django.contrib import admin
from .models import *

admin.site.register(OrderReason)
class OrderReasonAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'position', 'type')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(OrderType)
class OrderTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'color', 'position', 'is_default')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(Operator)
class OperatorAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'surname', 'phone', 'email', 'is_active')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'name', 'contract', 'supply_point', 'connection', 'address', 'operator', 'type', 'status', 'is_active')
    list_filter = ('created_at', 'updated_at', 'type', 'status')
    search_fields = ('token',)

admin.site.register(OrderObservation)
class RenameObservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'observation', 'created_at', 'updated_at', 'status', 'status_name', 'is_active', 'user')
    list_filter = ('created_at', 'updated_at', 'status')
    search_fields = ('order', 'observation')

admin.site.register(OrderReport)
class OrderReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'operator', 'dedicated_time', 'report_date', 'observation', 'document')
    list_filter = ('created_at', 'updated_at', 'order', 'operator', 'report_date')
    search_fields = ('order', 'operator', 'observation')

admin.site.register(OrderReportDocument)
class OrderReportDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order_report', 'file', 'created_at', 'updated_at', 'is_active')
    list_filter = ('created_at', 'updated_at', 'is_active')
    search_fields = ('order_report', 'file')