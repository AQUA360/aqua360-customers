from django.contrib import admin
from .models import  History

@admin.register(History)
class SearchTestAdmin(admin.ModelAdmin):
    list_display = ('query',)
    search_fields = ('query',)
    search_fields = ('query',)