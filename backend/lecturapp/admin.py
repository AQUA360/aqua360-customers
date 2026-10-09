from django.contrib import admin
from .models import ReadingOperator, Token

@admin.register(ReadingOperator)
class ReadingOperatorAdmin(admin.ModelAdmin):
    list_display = ['username', 'name', 'surname', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['username', 'name', 'surname']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'surname', 'username')
        }),
        ('Security', {
            'fields': ('password', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # Ensure password is hashed when saving through admin
        if 'password' in form.changed_data:
            obj.set_password(obj.password)
        super().save_model(request, obj, form, change)

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ['operator', 'token', 'created_at']
    list_filter = ['created_at']
    search_fields = ['operator__username', 'operator__name', 'token']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Token Information', {
            'fields': ('operator', 'token')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
