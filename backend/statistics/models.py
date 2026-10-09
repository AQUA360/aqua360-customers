from django.contrib.auth.models import User
from django.db import models
from contract.models import Contract
from documentmanager.models import Document
from service.models import SupplyPoint


class DailyDocumentStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name

class AccountingCode(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.token} - {self.name}" if self.token and self.name else f"AccountingCode {self.id}"

class AccountingValue(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    code = models.ForeignKey(AccountingCode, on_delete=models.CASCADE, null=True, blank=True, related_name='values')
    description = models.TextField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.token

class ReportType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class SupplyPointConsumption(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    period = models.IntegerField(null=False, blank=False)
    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.CASCADE, null=False, blank=False)
    consumption = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    daily_consumption = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.supply_point.name + " " + self.period + " - " + self.consumption

class ContractConsumption(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    period = models.IntegerField(null=False, blank=False)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=False, blank=False, related_name='consumption_stats')
    consumption = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    daily_consumption = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.contract.token + " " + str(self.period) + " - " + str(self.consumption)


class BillingReport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    start_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    end_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    type = models.CharField(max_length=255, null=False, blank=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=False, blank=False)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.type + " " + self.start_date.strftime("%Y-%m-%d") + " - " + self.end_date.strftime("%Y-%m-%d")

class GeneralReport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    start_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    end_date = models.DateTimeField(auto_now=True, null=True, blank=True)
    type = models.ForeignKey(ReportType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Report Type")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    # Filtres amb què es va generar l'informe (copiats des del ReportQueue corresponent,
    # units pel mateix document_id, en finalitzar la tasca a statistics/tasks.py::run_report_task).
    filters = models.JSONField(null=True, blank=True)
    filters_display = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.token if self.token else f"GeneralReport {self.id}"


class BillingConsumption(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    invoice = models.OneToOneField('billing.Invoice', on_delete=models.CASCADE, related_name='billing_consumption')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='billing_stats')
    
    year = models.IntegerField(null=True, blank=True)
    month = models.IntegerField(null=True, blank=True)
    
    # Consumption metrics
    consumption = models.FloatField(null=True, blank=True)
    consumption_days = models.IntegerField(null=True, blank=True)
    consumption_daily_avg = models.FloatField(null=True, blank=True)
    consumption_avg = models.FloatField(null=True, blank=True)
    
    # Financial metrics
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_amount_avg = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Billing Consumption"
        verbose_name_plural = "Billing Consumptions"

    def __str__(self):
        return f"Consumption for {self.invoice.token if self.invoice and self.invoice.token else self.id}"


class ReadingBatchExportColumn(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    value = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    def __str__(self):
        return self.name

class ReadingBatchImportTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    is_liters = models.BooleanField(default=False)

    def __str__(self):
        return self.name or f"ReadingBatchImportTemplate {self.id}"


class ReadingBatchImportColumn(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    original_name = models.CharField(max_length=255, null=True, blank=True)
    mapped_name = models.CharField(max_length=255, null=True, blank=True)
    template = models.ForeignKey(ReadingBatchImportTemplate, on_delete=models.CASCADE, null=True, blank=True, related_name='columns')

    def __str__(self):
        return self.original_name or self.mapped_name or f"ReadingBatchImportColumn {self.id}"

class AvailableReport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    # Dades de presentació
    name = models.CharField(max_length=255, verbose_name="Nom de l'informe")
    description = models.TextField(null=True, blank=True, verbose_name="Descripció de l'informe")
    is_active = models.BooleanField(default=True, verbose_name="Està activat")
    
    # Funció a cridar (mapejat directe a les claus de tasks.py)
    function_name = models.CharField(
        max_length=255, 
        verbose_name="Funció a cridar / Tasca Celery",
        help_text="Clau que s'utilitza a run_report_task de Celery (ex. 'accounting_values_report')"
    )
    
    # Secció a la qual correspon (relació amb el ReportType existent)
    section = models.ForeignKey(
        ReportType, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="available_reports",
        verbose_name="Secció a la qual correspon"
    )
    
    # Text del botó
    download_button_name = models.CharField(
        max_length=255, 
        default="Descarregar Excel", 
        verbose_name="Nom del botó de descàrrega"
    )
    
    # Control per a informes amb pantalles complexes a mida al front-end
    has_custom_config = models.BooleanField(
        default=False, 
        verbose_name="Té configuració personalitzada al front",
        help_text="Si està actiu, el front-end pintarà un formulari dissenyat a mida per a aquest informe."
    )
    
    # Camps necessaris en cas de formulari genèric (ex: ['start_date', 'end_date', 'exploitation_id'])
    required_fields = models.JSONField(
        default=list, 
        blank=True, 
        verbose_name="Camps requerits",
        help_text="Llista de camps que necessita el formulari genèric. Exemple: ['start_date', 'end_date', 'exploitation_id']"
    )
    
    # Resolució d'ordre de visualització
    position = models.IntegerField(default=0, verbose_name="Posició")

    class Meta:
        ordering = ['section__position', 'position', 'name']
        verbose_name = "Informe Disponible"
        verbose_name_plural = "Informes Disponibles"

    def __str__(self):
        section_name = self.section.name if self.section else "Sense secció"
        return f"{self.name} [{section_name}]"


class ReportQueue(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
        ('warning', 'Warning'),
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    report = models.ForeignKey(AvailableReport, on_delete=models.CASCADE, related_name='queue_items')
    payload = models.JSONField(null=True, blank=True)
    # Versio "humana" de payload (labels/noms en lloc d'ids crus), calculada a
    # AvailableReportViewSet.trigger via report_filters.resolve_filter_labels().
    filters_display = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    task_id = models.CharField(max_length=255, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Report Queue"
        verbose_name_plural = "Report Queues"
        ordering = ['created_at']

    def __str__(self):
        return f"ReportQueueItem {self.id} - {self.report.name if self.report else 'No report'} ({self.status})"


class DailyDocumentTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    available_report = models.ForeignKey(AvailableReport, on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_document_templates')
    days_to_complete = models.IntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name

class DailyDocument(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    document_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.ForeignKey(DailyDocumentStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_documents')
    template = models.ForeignKey(DailyDocumentTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_documents')
    
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='completed_daily_documents')
    
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_daily_documents')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_observation = models.TextField(null=True, blank=True)
    
    # add periodicity (daily, weekly, monthly)
    # add day of start in case of NOT daily
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)
    creation_error = models.TextField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.date.strftime("%Y-%m-%d")