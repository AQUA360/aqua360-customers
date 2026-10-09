from django.db import models
from django.utils.translation import gettext_lazy as _

from coredata.models import ConfigProject, Person, PersonBank
from documentmanager.models import Document
from lecturapp.models import ReadingOperator
from order.models import Operator, Order, OrderType
from pricing.models import Adjustment, LineItemType, PriceRate, Product, ProductOrigin, Tax
from contract.models import Bail, Contract, ContractClientType, ContractDebtManagement, ContractRequest, ContractStatus, ContractTerminationRequest, ContractUseType, PaymentType, PiggyBank, VariableType
from service.models import Company, CompanyBank, Connection, ConnectionRequest, Exploitation, Meter, Route, RouteZone, SupplyPoint
from django.contrib.auth.models import User

from verifactu.models import VerifactuNotification

# Taules Mestres

class PaymentStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "PaymentStatus ID {}".format(self.token)

class InvoiceStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "InvoiceStatus ID {}".format(self.token)

class JoinedPaymentStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "JoinedPaymentStatus ID {}".format(self.token)

class InvoiceSuppressionReason(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "InvoiceSuppressionReason ID {}".format(self.token)
    

class CommitmentDepositStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "CommitmentDepositStatus ID {}".format(self.token)
    

class PaymentCommitmentStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "PaymentCommitmentStatus ID {}".format(self.token)
    
class PaymentRemittanceStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "PaymentRemittanceStatus ID {}".format(self.token)

class InvoiceType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "InvoiceType ID {}".format(self.token)

class InvoiceCategory(models.Model):
    """Motiu/categoria de la factura (Consum, Pressupost, Canvi de nom, Alta,
    Alta d'escomesa, Reconnexió, Contra incendis, Recàrrec de retorn), independent
    del InvoiceType (Factura/Pressupost). `serie_digit_av`/`serie_digit_mv` configuren
    el primer caràcter (dígit de categoria) de la serie_final que genera aquesta
    categoria per a cada empresa (AV=1, MV=2, veure billing/models.py::Invoice.company),
    consumit a billing/utils/generate_serie_final_personalized.py::get_category_digit.
    Nomes s'aplica a factures normals: als pressupostos (is_budget=True) no els
    afecta, mantenen sempre la seva pròpia lògica de dígit."""
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    serie_digit_av = models.CharField(max_length=1, null=True, blank=True, verbose_name="Dígit de sèrie (AV)")
    serie_digit_mv = models.CharField(max_length=1, null=True, blank=True, verbose_name="Dígit de sèrie (MV)")

    def __str__(self):
        return self.name if self.name else "InvoiceCategory ID {}".format(self.token)

class InvoiceSerie(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"
    
class InvoiceClass(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
 
    def __str__(self):
        return f"{self.name}"

class ReadingAlert(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"
class ReaderAlert(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"

class RemoteReadingAlert(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"

class RejectMotiveType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name if self.name else "ReturnMotive ID {}".format(self.token)

class RejectMotive(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    type = models.ForeignKey(RejectMotiveType, on_delete=models.SET_NULL, null=True, blank=True, related_name="rejects")
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name if self.name else "ReturnMotive ID {}".format(self.token)
    
class InvoiceTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    origin = models.ForeignKey(ProductOrigin, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoice_templates")
    color = models.CharField(max_length=255, null=True, blank=True)
    file_template = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}"

class InvoiceWarning(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "CommitmentDeposit ID {}".format(self.token)

class Biller(models.Model):
    
    TYPE_CHOICES = [
        ('anual', 'Anual'),
        ('semestral', 'Semestral'),
        ('bimestral', 'Bimestral'),
        ('trimestral', 'Trimestral'),
        ('quadrimestral', 'Quadrimestral'),
        ('mensual', 'Mensual'),
    ]
    MONTH_CHOICES = [
        ('jan', 'Gener'),
        ('feb', 'Febrer'),
        ('mar', 'Març'),
        ('apr', 'Abril'),
        ('may', 'Maig'),
        ('jun', 'Juny'),
        ('jul', 'Juliol'),
        ('aug', 'Agost'),
        ('sep', 'Setembre'),
        ('oct', 'Octubre'),
        ('nov', 'Novembre'),
        ('dec', 'Desembre'),
    ]
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    period_type = models.CharField(choices=TYPE_CHOICES, default='trimestral')
    initial_month = models.CharField(choices=MONTH_CHOICES, default='jan')
    is_active = models.BooleanField(default=True)

class ReadingBatchTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    # biller = models.ForeignKey(Biller, on_delete=models.SET_NULL, null=True, blank=True, related_name='billing_batch_templates')
    is_active = models.BooleanField(default=True)

class BillingStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "BillingStatus ID {}".format(self.token)

class ConfigAca(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    exploitation = models.ForeignKey(Exploitation, on_delete=models.SET_NULL, null=True, blank=True)
    config_project = models.ForeignKey(ConfigProject, on_delete=models.SET_NULL, null=True, blank=True)
    token_type = models.CharField(max_length=255, null=True, blank=True)
    
    variable_types = models.ManyToManyField(VariableType, related_name='aca_variable_types', blank=True)
    contract_use_types = models.ManyToManyField(ContractUseType, related_name='aca_contract_use_types', blank=True)
    products = models.ManyToManyField(Product, related_name='aca_products', blank=True)
    price_rates = models.ManyToManyField(PriceRate, related_name='aca_price_rates', blank=True)
    
    is_active = models.BooleanField(default=True)
    last_changed_at = models.DateTimeField(null=True, blank=True)
    last_changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"ConfigAca {self.config_project.name} - {self.token}"

class Billing(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    biller = models.ForeignKey(Biller, on_delete=models.SET_NULL, null=True, blank=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.ForeignKey(BillingStatus, on_delete=models.SET_NULL, null=True, blank=True)
    communication_process = models.ForeignKey('communication.CommunicationProcess', on_delete=models.SET_NULL, null=True, blank=True)
    
    routes = models.ManyToManyField('service.Route', blank=True, related_name='billings')
    
    excluded_from = models.ForeignKey('billing.Billing', on_delete=models.SET_NULL, null=True, blank=True)
    is_excluded = models.BooleanField(default=False)
    billiing_archived = models.BooleanField(default=False)
    
    send_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Billing"
        verbose_name_plural = "Billings"


class BillingQueue(models.Model):
    TASK_TYPE_CHOICES = [
        ('PRE_INVOICE', _('Pre-invoice Generation')),
        ('DEFINITIVE_INVOICE', _('Definitive Invoice Generation')),
        ('REGENERATE_PDFS', _('Regeneració de PDFs de factures')),
        ('WINCEN_EXPORT', _('Exportació fitxer WinCen')),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    billing = models.ForeignKey(Billing, on_delete=models.CASCADE, related_name='queue_items')
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)
    payload = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    task_id = models.CharField(max_length=255, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    invoices_processed = models.IntegerField(default=0)
    documents_generated = models.IntegerField(default=0)
    file_url = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Billing Queue"
        verbose_name_plural = "Billing Queues"
        ordering = ['created_at']

    def __str__(self):
        return f"QueueItem {self.id} - {self.task_type} ({self.status}) for Billing {self.billing_id}"

# Taules Transaccions

class GeneralPayment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="General Payment Type")
    IBAN = models.ForeignKey(PersonBank, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="General Payment Person")
    company_iban = models.ForeignKey(CompanyBank, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="General Payment Company")
    #electronic invoice data
    dir3 = models.CharField(max_length=255, null=True, blank=True)
    accounting_office = models.CharField(max_length=255, null=True, blank=True)
    managing_body = models.CharField(max_length=255, null=True, blank=True)
    processing_unit = models.CharField(max_length=255, null=True, blank=True)
    command = models.CharField(max_length=255, null=True, blank=True)
    record = models.CharField(max_length=255, null=True, blank=True)
    
    mandate_id = models.CharField(max_length=255, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.token:
            if self.IBAN:
                return f"GeneralPayment token {self.token} - {self.IBAN.iban if self.IBAN.iban else 'No IBAN'}"
            elif self.company_iban:
                return f"GeneralPayment token {self.token} - {self.company_iban.iban if self.company_iban.iban else 'No IBAN'}"
            else:
                return f"GeneralPayment token {self.token}"
        else:
            return f"GeneralPayment ID {self.id}"

def sepa_template_upload_to(instance, filename):
    return f'uploads/documentations/sepa/template/{instance.id}/{filename}'

class GeneralPaymentMandateLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    general_payment = models.ForeignKey(GeneralPayment, on_delete=models.CASCADE, null=True, blank=True, related_name='mandate_logs')
    previous_mandate_id = models.CharField(max_length=255, null=True, blank=True)
    new_mandate_id = models.CharField(max_length=255, null=True, blank=True)
    is_manual = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    def __str__(self):
        return f"Mandate Log {self.id} - {self.general_payment.token}"

class GeneralPaymentSepaDocument(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    checked = models.BooleanField(default=False)
    file = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)
    template = models.FileField(upload_to=sepa_template_upload_to, null=True, blank=True)
    general_payment = models.OneToOneField(
        GeneralPayment,
        on_delete=models.CASCADE,
        related_name='sepa_document',
        null=True, blank=True
    )
    def __str__(self):
        return f"Document Sepa"

class ReadingBatchStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ReadingBatchStatus ID {}".format(self.token)

class BillingBatchStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "BillingBatchStatus ID {}".format(self.token)

class ReadingBatch(models.Model):
    TYPE_CHOICES = [
        ('ROUTE', 'Ruta'),
        ('DATE', 'Data')
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    type = models.CharField(choices=TYPE_CHOICES, default='DATE')
    routes = models.ManyToManyField('service.Route', blank=True, related_name='reading_batches')
    fix_meters = models.ManyToManyField('service.Meter', blank=True, related_name='reading_batches')
    status = models.ForeignKey(ReadingBatchStatus, on_delete=models.SET_NULL, null=True, blank=True)
    excluded_from = models.ForeignKey('billing.ReadingBatch', on_delete=models.SET_NULL, null=True, blank=True)
    
    include_telecontrol = models.BooleanField(default=False)
    include_manual = models.BooleanField(default=False)
    
    is_excluded = models.BooleanField(default=False)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    assign_readings_task_id = models.CharField(max_length=255, null=True, blank=True)
    estimating_task_id = models.CharField(max_length=255, null=True, blank=True)

    last_task_status = models.CharField(max_length=255, null=True, blank=True)
    last_task_errors = models.JSONField(null=True, blank=True)

    billing_missing = models.ForeignKey(Billing, on_delete=models.SET_NULL, null=True, blank=True, related_name='missing_batch')
    missing_start = models.DateField(null=True, blank=True)
    missing_end = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Reading Batch"
        verbose_name_plural = "Reading Batches"

    def __str__(self):
        return f"Batch {self.id} - {self.name or 'Unnamed'}"

# class ReadingRoute(models.Model):
#     created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
#     updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
#     token = models.CharField(max_length=255, null=True, blank=True)
#     name = models.CharField(max_length=255, null=True, blank=True)
#     description = models.TextField(null=True, blank=True)
#     route = models.ForeignKey(Route, on_delete=models.SET_NULL, null=True, blank=True)
#     operator = models.ForeignKey(Operator, on_delete=models.SET_NULL, null=True, blank=True)
#     is_control = models.BooleanField(default=False)
#     reading_batch = models.ForeignKey(ReadingBatch, related_name='reading_routes', on_delete=models.SET_NULL, null=True, blank=True)
#     billing = models.ForeignKey(Billing, related_name='reading_routes', on_delete=models.SET_NULL, null=True, blank=True)
    
#     is_active = models.BooleanField(default=True)
#     def __str__(self):
#         return f"Route {self.id} - {self.description or 'Unnamed'}"
    
def reading_document_upload_to(instance, filename):
    return f'uploads/billing/readings/{filename}'
    
class ReadingDocument(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_PROCESSED = 'processed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PROCESSED, 'Processed'),
        (STATUS_FAILED, 'Failed'),
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    file = models.FileField(upload_to=reading_document_upload_to, null=True, blank=True)
    batch = models.ForeignKey(ReadingBatch, on_delete=models.SET_NULL, related_name="documents", null=True, blank=True)
    template = models.ForeignKey(
        'statistics.ReadingBatchImportTemplate',
        on_delete=models.SET_NULL,
        related_name='reading_documents',
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    last_preview = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Reading document {self.token}"
    
class ReadingDocumentNotFound(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    reading_document = models.ForeignKey(ReadingDocument, on_delete=models.CASCADE, null=True, blank=True, related_name='not_found_readings')
    meter_code = models.CharField(max_length=255, null=True, blank=True)
    reading_value = models.IntegerField(null=True, blank=True)
    reading_date = models.DateField(null=True, blank=True)
    origin = models.CharField(max_length=255, null=True, blank=True)
    is_control = models.BooleanField(default=False)
    leak_value = models.IntegerField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"Reading document not found {self.token}"

class Reading(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    batch = models.ForeignKey(ReadingBatch, on_delete=models.SET_NULL, related_name="readings", null=True, blank=True)
    billing = models.ForeignKey(Billing, on_delete=models.SET_NULL, related_name="readings", null=True, blank=True)
    
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True)
    contract_request = models.ForeignKey(ContractRequest, on_delete=models.SET_NULL, null=True, blank=True)
    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.SET_NULL, null=True, blank=True)
    meter = models.ForeignKey(Meter, on_delete=models.SET_NULL, null=True, blank=True)
    reading_date = models.DateField(null=True, blank=True)
    reading_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    calculated_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    leak_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_used = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    consumption_days = models.IntegerField(null=True, blank=True)
    
    real_consumption = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    origin = models.CharField(max_length=255, null=True, blank=True)
    # reading_route = models.ForeignKey(ReadingRoute, related_name="readings", on_delete=models.SET_NULL, null=True, blank=True)
    previous_reading = models.ForeignKey('Reading', on_delete=models.SET_NULL, null=True, blank=True)
    is_control = models.BooleanField(default=False)
    is_estimated = models.BooleanField(default=False)
    is_close = models.BooleanField(default=False)
    is_initial = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    copied_from = models.ForeignKey('Reading', on_delete=models.SET_NULL, null=True, blank=True, related_name='copies')
    
    is_revised = models.BooleanField(default=False)
    
    #invoice = models.ForeignKey('billing.Invoice', on_delete=models.SET_NULL, null=True, blank=True)
    modified_readings = models.ManyToManyField('Reading', blank=True, related_name='original_readings')
    
    document = models.ForeignKey(ReadingDocument, related_name='readings', on_delete=models.SET_NULL, null=True, blank=True)
    
    reader_alert = models.ForeignKey(ReaderAlert, on_delete=models.SET_NULL, null=True, blank=True)
    operator = models.ForeignKey(ReadingOperator, on_delete=models.SET_NULL, null=True, blank=True)
    photo = models.ImageField(upload_to='uploads/billing/readings/photos/', null=True, blank=True)
    
    alert = models.ForeignKey(ReadingAlert, on_delete=models.SET_NULL, null=True, blank=True)
    remote_alert = models.ForeignKey(RemoteReadingAlert, on_delete=models.SET_NULL, null=True, blank=True)
    alert_notes = models.TextField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Reading"
        verbose_name_plural = "Readings"
        indexes = [
            # Cerca de "lectura anterior" a generate_consumption_invoice_multiple
            # (billing/utils/invoice_service.py): sense aquest index feia un Seq Scan
            # sobre tota la taula (~1M files, ~150ms per crida, un cop per lectura x
            # tarifa dins del lot de facturacio).
            models.Index(fields=['supply_point', 'meter', 'contract', '-reading_date'], name='reading_prev_contract_idx'),
            # Fallback quan la cerca amb contract no troba res (mateixa funcio).
            models.Index(fields=['supply_point', 'meter', '-reading_date'], name='reading_prev_no_contract_idx'),
        ]

    @property
    def is_fire(self):
        from coredata.models import ConfigProject
        from coredata.utils.fire_usage_utils import get_fire_usage_tokens
        fire_usage_tokens = get_fire_usage_tokens()

        try:
            fire_connection_token = ConfigProject.objects.get(token='fire_connection_use_type_token').value
        except ConfigProject.DoesNotExist:
            fire_connection_token = 'incendis'

        is_fire_contract = self.contract and self.contract.use_type and self.contract.use_type.token in fire_usage_tokens
        is_fire_connection = self.supply_point and self.supply_point.connection and self.supply_point.connection.use_type and self.supply_point.connection.use_type.token == fire_connection_token

        return bool(is_fire_contract or is_fire_connection)

    def __str__(self):
        return f"Pending Reading for Meter {self.meter.id if self.meter else 'No meter'} on {self.reading_date}"
    
class BillingBatch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    # template = models.ForeignKey(BillingBatchTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey(BillingBatchStatus, on_delete=models.SET_NULL, null=True, blank=True)
    billing = models.ForeignKey(Billing, on_delete=models.SET_NULL, null=True, blank=True, related_name='billing_batches')
    processed_at = models.DateTimeField(null=True, blank=True)
    
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    send_at = models.DateTimeField(null=True, blank=True)
    
    excluded_from = models.ForeignKey('billing.BillingBatch', on_delete=models.SET_NULL, null=True, blank=True)
    is_excluded = models.BooleanField(default=False)
    is_processed = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Billing Batch"
        verbose_name_plural = "Billing Batches"

    def __str__(self):
        return f"Batch {self.id} - Unnamed"

class EstimatedBag(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)

    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.SET_NULL, null=True, blank=True, related_name='estimated_bag')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='estimated_bags')
    total_consumption = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"Estimated Bag {self.token} - {self.supply_point.name}"
    
class EstimatedBagMovement(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    movement_date = models.DateField(null=True, blank=True)
    
    estimated_bag = models.ForeignKey(EstimatedBag, on_delete=models.CASCADE, related_name='movements')
    reading = models.ForeignKey(Reading, on_delete=models.SET_NULL, null=True, blank=True, related_name='estimated_bag_movements')
    invoice = models.ForeignKey('Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='estimated_bag_movements')
    
    is_positive = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Estimated Bag Movement {self.token} - {self.amount}"

def invoice_request_upload_to(instance, filename):
    return f'uploads/billing/invoices/{instance.id}/{filename}'

class Invoice(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    connection = models.ForeignKey(Connection, on_delete=models.SET_NULL, null=True, blank=True)
    connection_request = models.ForeignKey(ConnectionRequest, on_delete=models.SET_NULL, null=True, blank=True)
    exploitation = models.ForeignKey(Exploitation, on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True)
    batch = models.ForeignKey(BillingBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    billing = models.ForeignKey(Billing, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    template = models.ForeignKey(InvoiceTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_file_template = models.FileField(upload_to=invoice_request_upload_to, null=True, blank=True)
    invoice_file = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)

    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    contract_request = models.ForeignKey(ContractRequest, on_delete=models.SET_NULL, null=True, blank=True)
    contract_termination = models.ForeignKey(ContractTerminationRequest, on_delete=models.SET_NULL, null=True, blank=True)
    piggy_bank = models.ForeignKey(PiggyBank, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True)
    payment_bank = models.ForeignKey(PersonBank, on_delete=models.SET_NULL, null=True, blank=True)
    payment_company_bank = models.ForeignKey(CompanyBank, on_delete=models.SET_NULL, null=True, blank=True)
    serie = models.ForeignKey(InvoiceSerie, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_class = models.ForeignKey(InvoiceClass, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(InvoiceType, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(InvoiceCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    number = models.CharField(max_length=255, null=True, blank=True)
    used_aca = models.CharField(max_length=255, null=True, blank=True)

    dir3_final = models.CharField(max_length=255, null=True, blank=True)
    accounting_office_final = models.CharField(max_length=255, null=True, blank=True)
    managing_body_final = models.CharField(max_length=255, null=True, blank=True)
    processing_unit_final = models.CharField(max_length=255, null=True, blank=True)
    command_final = models.CharField(max_length=255, null=True, blank=True)
    record_final = models.CharField(max_length=255, null=True, blank=True)
 
    type_final = models.CharField(max_length=10, null=True, blank=True)
    serie_final = models.CharField(max_length=100, null=True, blank=True, unique=True)
    serie_token_final = models.CharField(max_length=255, null=True, blank=True)
    invoice_class_token_final = models.CharField(max_length=255, null=True, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    title_final = models.CharField(max_length=255, null=True, blank=True)
    reject = models.ForeignKey(RejectMotive, on_delete=models.SET_NULL, null=True, blank=True)

    is_confirmed = models.BooleanField(default=False)
    customer_final = models.CharField(max_length=255, null=True, blank=True)
    customer_token_final = models.CharField(max_length=255, null=True, blank=True)
    payer_final = models.CharField(max_length=255, null=True, blank=True)
    payer_token_final = models.CharField(max_length=255, null=True, blank=True)
    customer_is_juridic = models.BooleanField(default=False)
    customer_tlf_final = models.CharField(max_length=255, null=True, blank=True)
    customer_email_final = models.CharField(max_length=255, null=True, blank=True)
    address_final = models.CharField(max_length=255, null=True, blank=True)
    postal_code_final = models.CharField(max_length=255, null=True, blank=True)
    city_final = models.CharField(max_length=255, null=True, blank=True)
    province_final = models.CharField(max_length=255, null=True, blank=True)
    location_final = models.CharField(max_length=255, null=True, blank=True)
    country_final = models.CharField(max_length=255, null=True, blank=True)
    subtotal_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    left_to_pay = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)

    payment_type_final = models.CharField(max_length=255, null=True, blank=True)
    payment_type_token_final = models.CharField(max_length=255, null=True, blank=True)
    #bank_final = models.CharField(max_length=255, null=True, blank=True)
    payment_bank_final = models.CharField(max_length=255, null=True, blank=True)
    payment_swift_final = models.CharField(max_length=255, null=True, blank=True)
    payment_iban_final = models.CharField(max_length=255, null=True, blank=True)
    persons_final = models.IntegerField(null=True, blank=True)
    responsible_consumption = models.BooleanField(default=True)

    status = models.ForeignKey(InvoiceStatus, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    
    return_token = models.CharField(max_length=255, null=True, blank=True)
    is_suppressed = models.BooleanField(default=False)
    is_excluded = models.BooleanField(default=False)
    reviewed = models.BooleanField(default=False)
    suppression_reason = models.ForeignKey(InvoiceSuppressionReason, on_delete=models.SET_NULL, null=True, blank=True)
    suppressed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    suppressed_at = models.DateTimeField(null=True, blank=True)
    
    is_general = models.BooleanField(default=False)
    general_contracts = models.ManyToManyField(Contract, blank=True, related_name="general_invoices")
    
    simplified = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    send_at = models.DateTimeField(null=True, blank=True)
    
    parent_invoice = models.ForeignKey('billing.Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name="child_invoices")

    real_consumption = models.FloatField(null=True, blank=True)
    consumption = models.FloatField(null=True, blank=True)
    consumption_days = models.IntegerField(null=True, blank=True)
    readings = models.ManyToManyField(Reading, blank=True, related_name='invoices')
    #reading_last = models.ForeignKey(Reading, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices_last")
    origin = models.ForeignKey(ProductOrigin, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    is_registration = models.BooleanField(default=False)
    
    billing_period_year = models.IntegerField(null=True, blank=True)
    billing_period_month = models.IntegerField(null=True, blank=True)
    billing_period_days = models.IntegerField(null=True, blank=True)
    
    budget_token = models.CharField(max_length=255, null=True, blank=True)
    refactored_token = models.CharField(max_length=255, null=True, blank=True)
    budget_comment = models.TextField(null=True, blank=True)
    
    warning = models.ForeignKey(InvoiceWarning, on_delete=models.SET_NULL, null=True, blank=True)
    
    manually_modified = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    
    # Verifactu
    
    verifactu_notification = models.ForeignKey(VerifactuNotification, on_delete=models.SET_NULL, null=True, blank=True)
    
    
    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        
    def __str__(self):
        return f"Invoice {self.token} - {self.title_final if self.title_final else 'Unnamed'}"
    

class InvoiceLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='invoice_logs')
    field_name = models.TextField(null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    operation_token = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Prevent updates - only allow creation
        if self.pk:
            raise ValueError("InvoiceLog entries cannot be modified. They are create-only.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Prevent deletion
        raise ValueError("InvoiceLog entries cannot be deleted. They are create-only.")
    
    def __str__(self):
        return f'InvoiceLog {self.id}'


class InvoiceSequence(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    prefix = models.CharField(max_length=32, unique=True)
    last_number = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Invoice Sequence"
        verbose_name_plural = "Invoice Sequences"

    def __str__(self):
        return f"Sequence {self.prefix}: {self.last_number}"


class AppliedAdjustment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    adjustment = models.ForeignKey(Adjustment, on_delete=models.SET_NULL, null=True, blank=True, related_name="applied_adjustments")
    total_applied = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    is_minimum = models.BooleanField(default=False)
    is_vulnerable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Applied Adjustment {self.token} - {self.name}"
    

class InvoiceLineItem(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True)

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name="line_items")
    reading = models.ForeignKey(Reading, on_delete=models.SET_NULL, null=True, blank=True, related_name="line_items")
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name="line_items")
    line_item_type = models.ForeignKey(LineItemType, on_delete=models.SET_NULL, null=True, blank=True, related_name="line_items")
    price_rate = models.ForeignKey(PriceRate, on_delete=models.SET_NULL, null=True, blank=True)
    price_rate_name = models.CharField(max_length=255, null=True, blank=True)
    product = models.ForeignKey(Product, related_name='line_items', on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=255, null=True, blank=True)

    tax = models.ForeignKey(Tax, on_delete=models.SET_NULL, null=True, blank=True)

    price = models.FloatField(null=True, blank=True)
    price_unit = models.FloatField(null=True, blank=True)
    units = models.FloatField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    interval = models.IntegerField(null=True, blank=True)
    end_stretch = models.IntegerField(null=True, blank=True)
    adjustments = models.ManyToManyField(AppliedAdjustment, blank=True, related_name='line_items')

    tax_percent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax_price = models.FloatField(null=True, blank=True)
    total = models.DecimalField(max_digits=11, decimal_places=4, null=True, blank=True)

    manually_modified = models.BooleanField(default=False)
    manually_added = models.BooleanField(default=False)

    custom_order = models.IntegerField(null=True, blank=True, default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['custom_order', 'id']

    def __str__(self):
        return f"{self.description} - {self.price}"

    def save(self, *args, **kwargs):
        # Align sign of tax_price to match the sign of price
        if self.price is not None and self.tax_price is not None:
            if self.price < 0:
                self.tax_price = -abs(self.tax_price)
            elif self.price > 0:
                self.tax_price = abs(self.tax_price)

        # Recalculate total if price is set
        if self.price is not None:
            tax_val = self.tax_price if self.tax_price is not None else 0.0
            total_val = float(self.price) + float(tax_val)
            
            # Constrain total to database field limits (max_digits=11, decimal_places=4)
            from decimal import Decimal, ROUND_HALF_UP
            try:
                decimal_value = Decimal(str(total_val))
                MAX_TOTAL = Decimal('9999999.9999')
                MIN_TOTAL = Decimal('-9999999.9999')
                if decimal_value > MAX_TOTAL:
                    decimal_value = MAX_TOTAL
                elif decimal_value < MIN_TOTAL:
                    decimal_value = MIN_TOTAL
                self.total = decimal_value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            except Exception:
                self.total = Decimal(str(round(total_val, 4)))

        super().save(*args, **kwargs)


class Payment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True, unique=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    status = models.ForeignKey(PaymentStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    commitment_deposit = models.ForeignKey('billing.CommitmentDeposit', on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments", null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    sent_date = models.DateField(null=True, blank=True)     #Used for SEPA
    paid_at = models.DateField(null=True, blank=True)
    
    due_date = models.DateField(null=True, blank=True)
    payment_type = models.CharField(max_length=255, null=True, blank=True)
    payment_type_token = models.CharField(max_length=255, null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    payment_bank = models.CharField(max_length=255, null=True, blank=True)
    payment_swift = models.CharField(max_length=255, null=True, blank=True)
    
    customer_final = models.CharField(max_length=255, null=True, blank=True)
    customer_token_final = models.CharField(max_length=255, null=True, blank=True)
    payer_final = models.CharField(max_length=255, null=True, blank=True)
    payer_token_final = models.CharField(max_length=255, null=True, blank=True)
    address_final = models.CharField(max_length=255, null=True, blank=True)
    location_final = models.CharField(max_length=255, null=True, blank=True)
    
    reject_date = models.DateField(null=True, blank=True)
    reject = models.ForeignKey(RejectMotive, on_delete=models.SET_NULL, null=True, blank=True)
    
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    
    PAYMENT_ORIGIN_CHOICES = [
        ('box_office', _('Box Office')),
        ('post_office', _('Post Office')),
    ]
    payment_origin_choice = models.CharField(max_length=20, choices=PAYMENT_ORIGIN_CHOICES, null=True, blank=True)
    
    is_excluded = models.BooleanField(default=False)
    is_duplicate = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
    
    def __str__(self):
        return f"Payment {self.token} of {self.amount} for Invoice {self.invoice.token if self.invoice else 'No invoice'}"


class PaymentRemittance(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)     #msgId
    
    status = models.ForeignKey(PaymentRemittanceStatus, on_delete=models.SET_NULL, null=True, blank=True)
    payments = models.ManyToManyField(Payment, blank=True, related_name='remittances')
    company_bank = models.ForeignKey(CompanyBank, on_delete=models.SET_NULL, null=True, blank=True)
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    desired_send_at = models.DateField(null=True, blank=True)
    sent_at = models.DateField(null=True, blank=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_return = models.BooleanField(default=False)
    
    task_id = models.CharField(max_length=255, null=True, blank=True)
    
    pending_changes = models.BooleanField(default=False)
    def __str__(self):
        return f"Remittance {self.token} of {self.payments.count()} payments"
    

class PaymentRemittanceReturn(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)     
    
    return_date = models.DateField(null=True, blank=True)
    returned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    payments = models.ManyToManyField(Payment, blank=True, related_name='remittances_returns')
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Remittance return {self.token} of {self.payments.count()} payments"

class PaymentMovement(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True, related_name='movements')
    
    movement_date = models.DateField(null=True, blank=True)
    payment_bank = models.CharField(max_length=255, null=True, blank=True)
    payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True)
    
    payoff_invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='payoff_movements')
    previous_status = models.ForeignKey(PaymentStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='movement_previous_status')
    current_status = models.ForeignKey(PaymentStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='movement_current_status')
    
    reject_motive = models.ForeignKey(RejectMotive, on_delete=models.SET_NULL, null=True, blank=True)
    payment_remittance = models.ForeignKey(PaymentRemittance, on_delete=models.SET_NULL, null=True, blank=True, related_name='movements')
    
    is_positive = models.BooleanField(default=True, null=True, blank=True)
    
    PAYMENT_ORIGIN_CHOICES = [
        ('box_office', _('Box Office')),
        ('post_office', _('Post Office')),
    ]
    payment_origin = models.CharField(max_length=20, choices=PAYMENT_ORIGIN_CHOICES, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Payment Movement {self.token} of {self.payment.token}"

class CommitmentDeposit(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True, unique=True)
    
    status = models.ForeignKey(CommitmentDepositStatus, on_delete=models.SET_NULL, null=True, blank=True)
    
    total = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True, default=0.00)
    remaining = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True, default=0.00)
    remaining_to_share = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True, default=0.00)
    
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    days_next_payment = models.IntegerField(null=True, blank=True)
    
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='commitment_deposits')
    invoices = models.ManyToManyField(Invoice, blank=True, related_name='payment_commitments')
    
    customer_final = models.CharField(max_length=255, null=True, blank=True)
    customer_token_final = models.CharField(max_length=255, null=True, blank=True)
    address_final = models.CharField(max_length=255, null=True, blank=True)
    location_final = models.CharField(max_length=255, null=True, blank=True)
    persons_final = models.IntegerField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Commitment Deposit"
        verbose_name_plural = "Commitment Deposits"
        
    def __str__(self):
        return f"Commitment Deposit {self.token} of {self.total}"


class JoinedPayment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    token = models.CharField(max_length=255, null=True, blank=True)
    number = models.CharField(max_length=255, null=True, blank=True)
    
    status = models.ForeignKey(JoinedPaymentStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='joined_payments')
    payments = models.ManyToManyField(Payment, blank=True, related_name='joined_payments')
    
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='joined_payments')
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='joined_payments')
    
    customer_final = models.CharField(max_length=255, null=True, blank=True)
    customer_token_final = models.CharField(max_length=255, null=True, blank=True)
    
    payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True)
    payment_type_name = models.CharField(max_length=255, null=True, blank=True)
    payment_type_token = models.CharField(max_length=255, null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    
    total_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    claim_request = models.ForeignKey('claimrequest.ClaimRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='joined_payments')
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Joined Payment {self.token} of {self.payments.count()} payments"

class JoinedPaymentObservation(models.Model):
    joined_payment = models.ForeignKey(JoinedPayment, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(JoinedPaymentStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "JoinedPaymentObservation {}".format(self.id)

class PaymentCommitment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    status = models.ForeignKey(PaymentCommitmentStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_commitments')
    commitment_deposit = models.ForeignKey(CommitmentDeposit, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_commitments')
    
    is_guide = models.BooleanField(default=False)
    currently_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True)
    payment_bank = models.ForeignKey(PersonBank, on_delete=models.SET_NULL, null=True, blank=True)
    payment_bank_final = models.CharField(max_length=255, null=True, blank=True)
    payment_swift_final = models.CharField(max_length=255, null=True, blank=True)
    
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Payment Commitment {self.token} of {self.amount}"

class CommitmentDepositObservation(models.Model):
    commitment_deposit = models.ForeignKey(CommitmentDeposit, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(CommitmentDepositStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "CommitmentDepositObservation {}".format(self.id)

class Message(models.Model):
    TYPE_CHOICES = [
        ('TEXT', 'Text'),
        ('GRAPHIC', 'Gràfic')
    ]
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    start_at = models.DateField(null=True, blank=True)
    end_at = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    message_type = models.CharField(choices=TYPE_CHOICES, default='TEXT', max_length=10)
    
    invoices = models.ManyToManyField(Invoice, blank=True, related_name='messages')
    template = models.ForeignKey(InvoiceTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages")
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"Message {self.id}"

class MessageCondition(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name="conditions")
    name = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.JSONField(null=True, blank=True)
    OPERATION_CHOICES=[
        ('eq', 'Equal'),
        ('ne', 'Not Equal'),
        ('gt', 'Greater Than'),
        ('lt', 'Less Than'),
        ('ge', 'Greater or Equal'),
        ('le', 'Less or Equal'),
        ('in', 'In'),
        ('ni', 'Not In'),
        ('is_true', 'Is True'),
        ('is_false', 'Is False'),
        ('is_null', 'Is Null'),
        ('is_not_null', 'Is Not Null')
    ]
    operation = models.CharField(choices=OPERATION_CHOICES, default='eq')
    formula = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.name}"

class DocumentSEPALine(models.Model):
    line_number = models.IntegerField(null=True, blank=True)
    payments = models.ManyToManyField(Payment, blank=True, related_name='sepa_lines')

class DocumentSEPA(models.Model):
    date = models.DateField(auto_now_add=True)
    lines = models.ManyToManyField(DocumentSEPALine, blank=True, related_name='sepas')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)
    invoices = models.ManyToManyField(Invoice, blank=True, related_name='sepa_documents')
    commitment_deposits = models.ManyToManyField(CommitmentDeposit, blank=True, related_name='sepa_documents') 
    msgId = models.CharField(max_length=255, null=True, blank=True, unique=True)

class BankRNDDocument(models.Model): # Done to avoid repeated payments when entering more than once the document
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True, unique=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    first_line = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f"Bank RND Document {self.token}"