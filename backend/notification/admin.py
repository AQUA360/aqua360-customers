from django.contrib import admin

# Register your models here.
from .models import *

admin.site.register(Notification)   
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'description', 'module', 'entity', 'object_id', 'is_seen', 'is_active')
    list_filter = ('is_seen', 'is_active')
    search_fields = ('token', 'name', 'description', 'module', 'entity', 'object_id')
    

admin.site.register(CalendarTask)
class CalendarTaskAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'description', 'set_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('token', 'name', 'description', 'set_date')

admin.site.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'description', 'contract', 'invoice', 'status', 'tasks', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('token', 'name', 'description', 'contract', 'invoice')

admin.site.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ('incident', 'description', 'user', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('incident', 'description', 'user')

admin.site.register(IncidentStatus)
class IncidentStatusAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'color', 'position', 'is_default')
    list_filter = ('is_default',)
    search_fields = ('token', 'name', 'color', 'position')

admin.site.register(IncidentType)
class IncidentTypeAdmin(admin.ModelAdmin):
    list_display = ('token', 'name', 'position', 'is_default')
    list_filter = ('is_default',)
    search_fields = ('token', 'name', 'position')

admin.site.register(GeneralNote)
class GeneralNoteAdmin(admin.ModelAdmin):
    list_display = ('token', 'title', 'description', 'user', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('token', 'title', 'description', 'user')
