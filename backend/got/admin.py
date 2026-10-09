from django.contrib import admin

from got.models import OrderForm

# Register your models here.
@admin.register(OrderForm)
class OrderFormAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'order_type','structure', 'created_at', 'updated_at')
    search_fields = ('name',)
    list_filter = ('order_type', 'created_at', 'updated_at')