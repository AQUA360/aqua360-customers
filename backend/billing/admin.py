from django.contrib import admin

from .models import *

class ReadingAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(Reading, ReadingAdmin)

class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'serie_final', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at', 'token')
    search_fields = ('token', 'id')

admin.site.register(Invoice, InvoiceAdmin)

class ReadingBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
    ordering = ('-created_at',)

admin.site.register(ReadingBatch, ReadingBatchAdmin)

class InvoiceTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)
    
admin.site.register(InvoiceType, InvoiceTypeAdmin)

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(Payment, PaymentAdmin)

class InvoiceLineItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(InvoiceLineItem, InvoiceLineItemAdmin)

class DocumentSEPAAdmin(admin.ModelAdmin):
    list_display = ('id', 'date')

admin.site.register(DocumentSEPA, DocumentSEPAAdmin)

class DocumentSEPALineAdmin(admin.ModelAdmin):
    list_display = ('id', 'line_number')

admin.site.register(DocumentSEPALine, DocumentSEPALineAdmin)

class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'title')

admin.site.register(Message, MessageAdmin)

class InvoiceTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'origin')

admin.site.register(InvoiceTemplate, InvoiceTemplateAdmin)

class RejectMotiveAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'description')

admin.site.register(RejectMotive, RejectMotiveAdmin)

class GeneralPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'type', 'company_iban', 'IBAN')

admin.site.register(GeneralPayment, GeneralPaymentAdmin)

class PaymentStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

admin.site.register(PaymentStatus, PaymentStatusAdmin)

class CommitmentDepositAdmin(admin.ModelAdmin):
    list_display = ('id', 'token')

admin.site.register(CommitmentDeposit, CommitmentDepositAdmin)

class PaymentCommitmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'token')

admin.site.register(PaymentCommitment, PaymentCommitmentAdmin)

class BillingAdmin(admin.ModelAdmin):
    list_display = ('id', 'token')

admin.site.register(Billing, BillingAdmin)

class BillingBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

admin.site.register(BillingBatch, BillingBatchAdmin)

class PaymentRemittanceAdmin(admin.ModelAdmin):
    list_display = ('id', 'token')

admin.site.register(PaymentRemittance, PaymentRemittanceAdmin)



class InvoiceSerieAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'token')

admin.site.register(InvoiceSerie, InvoiceSerieAdmin)

class InvoiceClassAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'token')

admin.site.register(InvoiceClass, InvoiceClassAdmin)

class ReadingAlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'token')

admin.site.register(ReadingAlert, ReadingAlertAdmin)

class RejectMotiveTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'token')

admin.site.register(RejectMotiveType, RejectMotiveTypeAdmin)

class InvoiceWarningAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'token')

admin.site.register(InvoiceWarning, InvoiceWarningAdmin)

class BillerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'token', 'period_type')

admin.site.register(Biller, BillerAdmin)

class ReadingBatchTemplateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'token')

admin.site.register(ReadingBatchTemplate, ReadingBatchTemplateAdmin)



class GeneralPaymentSepaDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'general_payment', 'checked')

admin.site.register(GeneralPaymentSepaDocument, GeneralPaymentSepaDocumentAdmin)



class ReadingDocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'batch')

admin.site.register(ReadingDocument, ReadingDocumentAdmin)

class EstimatedBagAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'supply_point', 'contract')

admin.site.register(EstimatedBag, EstimatedBagAdmin)

class CommitmentDepositObservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'commitment_deposit', 'observation', 'status')

admin.site.register(CommitmentDepositObservation, CommitmentDepositObservationAdmin)

class MessageConditionAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'name', 'operation')

admin.site.register(MessageCondition, MessageConditionAdmin)

class InvoiceSuppressionReasonAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'token')

admin.site.register(InvoiceSuppressionReason, InvoiceSuppressionReasonAdmin)