from django.contrib import admin

from .models import *

admin.site.register(MessageType)
class MessageTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(MessageOrigin)
class MessageOriginAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(CommunicationStatus)
class CommunicationStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(CommunicationProcessStatus)
class CommunicationProcessStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)


admin.site.register(MessageTypeTemplate)
class MessageTypeTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(Communication)
class CommunicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(CommunicationProcess)
class CommunicationProcessAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(CommunicationFile)
class CommunicationFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)