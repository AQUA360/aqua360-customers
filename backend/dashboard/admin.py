from django.contrib import admin

from .models import UserDashboard, UserSidebarLayout


@admin.register(UserDashboard)
class UserDashboardAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserSidebarLayout)
class UserSidebarLayoutAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')
