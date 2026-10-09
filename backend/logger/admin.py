from django.contrib import admin

from .models import *

admin.site.register(LogCommitmentDepositMovement)
class LogCommitmentDepositMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'timestamp', 'object', 'previous_status', 'current_status', 'new_payment', 'paid_invoice', 'user')
    list_filter = ('timestamp', 'object', 'previous_status', 'current_status', 'new_payment', 'paid_invoice', 'user')
    search_fields = ('timestamp', 'object', 'previous_status', 'current_status', 'new_payment', 'paid_invoice', 'user')