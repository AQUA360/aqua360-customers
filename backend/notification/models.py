from django.db import models
from django.contrib.auth.models import Group, User

from billing.models import CommitmentDeposit, Invoice
from contract.models import Contract
from documentmanager.models import Document
from order.models import Order
from service.models import Cluster, SupplyCut, SupplyPoint


class IncidentStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    # Fase de tramitació a què correspon l'estat (informativa i per a informes)
    PHASE_REGISTRATION = 'registration'
    PHASE_CLASSIFICATION = 'classification'
    PHASE_ASSIGNMENT = 'assignment'
    PHASE_PROCESSING = 'processing'
    PHASE_RESOLUTION = 'resolution'
    PHASE_CLOSING = 'closing'
    PHASE_CHOICES = [
        (PHASE_REGISTRATION, 'Registre'),
        (PHASE_CLASSIFICATION, 'Classificació'),
        (PHASE_ASSIGNMENT, 'Assignació'),
        (PHASE_PROCESSING, 'Tramitació'),
        (PHASE_RESOLUTION, 'Resolució'),
        (PHASE_CLOSING, 'Tancament'),
    ]
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, null=True, blank=True)
    # Mentre la incidència és en aquest estat el termini no corre (p. ex. pendent de subsanació)
    pauses_due = models.BooleanField(default=False)
    # Avís si la pausa supera aquests dies hàbils
    max_pause_days = models.PositiveIntegerField(null=True, blank=True)
    # Estats als quals es pot passar des d'aquest; si no n'hi ha cap, a qualsevol
    allowed_next = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='+')

    def __str__(self):
        return self.name if self.name else "IncidentStatus ID {}".format(self.token)
    
class IncidentType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    # Termini per resoldre les incidències d'aquest tipus (buit: sense venciment).
    # L'avís previ i l'escalat es compten en la mateixa unitat que el termini.
    UNIT_BUSINESS_DAYS = 'business_days'
    UNIT_NATURAL_DAYS = 'natural_days'
    UNIT_HOURS = 'hours'
    UNIT_CHOICES = [
        (UNIT_BUSINESS_DAYS, 'Dies hàbils'),
        (UNIT_NATURAL_DAYS, 'Dies naturals'),
        (UNIT_HOURS, 'Hores'),
    ]
    due_term = models.PositiveIntegerField(null=True, blank=True)
    due_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default=UNIT_BUSINESS_DAYS)
    warning_before = models.PositiveIntegerField(null=True, blank=True)
    escalation_after = models.PositiveIntegerField(null=True, blank=True)
    escalation_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    escalation_group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    # Text proposat en tancar-la (resolució motivada) i del justificant de registre
    resolution_template = models.TextField(null=True, blank=True)
    receipt_text = models.TextField(null=True, blank=True)
    send_receipt = models.BooleanField(default=False)
    # Mentre n'hi ha una d'oberta, el contracte es marca per no fer-hi ofertes comercials
    blocks_commercial = models.BooleanField(default=False)
    
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name if self.name else "ContractUseType ID {}".format(self.token)
    
class Notification(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    module = models.CharField(max_length=255, null=True, blank=True)
    entity = models.CharField(max_length=255, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    
    is_seen = models.BooleanField(default=False)
    read_by = models.ManyToManyField(User, blank=True, related_name='read_notifications')
    archived_by = models.ManyToManyField(User, blank=True, related_name='archived_notifications')
    is_active = models.BooleanField(default=True)
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    #TODO:MISSING ROLE/GROUP
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return self.name if self.name else "Notification ID {}".format(self.token)


class CalendarTaskRecurrence(models.Model):
    """
    Regla d'una tasca recurrent. Les ocurrències són CalendarTask normals que es
    generen per endavant (vegeu notification.utils.recurrence), de manera que cada
    una es pot marcar com a feta o editar per separat. Els camps name/description/
    color/user són la plantilla de les ocurrències que es generin a partir d'ara.
    """
    FREQUENCY_DAILY = 'daily'
    FREQUENCY_WEEKLY = 'weekly'
    FREQUENCY_MONTHLY = 'monthly'
    FREQUENCY_YEARLY = 'yearly'
    FREQUENCY_CHOICES = [
        (FREQUENCY_DAILY, 'Diària'),
        (FREQUENCY_WEEKLY, 'Setmanal'),
        (FREQUENCY_MONTHLY, 'Mensual'),
        (FREQUENCY_YEARLY, 'Anual'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)

    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default=FREQUENCY_WEEKLY)
    interval = models.PositiveIntegerField(default=1)
    # Dies de la setmana (0=dilluns ... 6=diumenge), només per a la freqüència setmanal.
    weekdays = models.JSONField(default=list, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    # Última data per a la qual ja s'han generat ocurrències.
    generated_until = models.DateField(null=True, blank=True)

    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='calendar_task_recurrences')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Calendar Task Recurrence"
        verbose_name_plural = "Calendar Task Recurrences"

    def __str__(self):
        """Return the recurrence name or a label containing its ID."""
        return self.name if self.name else "Calendar Task Recurrence ID {}".format(self.id)


class CalendarTask(models.Model):
    SOURCE_MANUAL = 'manual'
    SOURCE_AUTO = 'auto'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_AUTO, 'Automàtica'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    task_done = models.BooleanField(default=False)
    #TODO:MISSING ROLE/GROUP
    
    #contract
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='calendar_tasks')
    
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='calendar_tasks')

    set_date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    recurrence = models.ForeignKey(CalendarTaskRecurrence, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')

    # Les tasques automàtiques les crea el sistema (p. ex. un canvi de comptador
    # pendent d'aplicar) i es tanquen soles quan es resol el que les ha originat.
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    source_key = models.CharField(max_length=100, null=True, blank=True)

    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    # Quan se n'ha avisat (notificació/correu), per no repetir l'avís cada dia.
    notified_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Calendar Task"
        verbose_name_plural = "Calendar Tasks"
        
    def __str__(self):
        return self.name if self.name else "Calendar Task ID {}".format(self.id)
    

class NotificationPreference(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preference')
    # Correu diari amb les tasques pendents del dia i les endarrerides.
    email_daily_tasks = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        """Return a notification preference label identifying its user."""
        return "Notification Preference of {}".format(self.user_id)


class GeneralNote(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)

    note = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    read_by = models.ManyToManyField(User, blank=True, related_name='read_general_notes')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "General Note"
        verbose_name_plural = "General Notes"
        
    def __str__(self):
        return self.token if self.token else "General Notes ID {}".format(self.id)

class IncidentChannel(models.Model):
    """Canal d'entrada de la incidència (telèfon, correu, presencial, oficina virtual...)."""
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "IncidentChannel ID {}".format(self.token)


class Incident(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    commitment_deposit = models.ForeignKey(CommitmentDeposit, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    order_incident = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    cluster = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    supply_cut = models.ForeignKey(SupplyCut, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    tasks = models.ManyToManyField(CalendarTask, blank=True, related_name='incidents')

    status = models.ForeignKey(IncidentStatus, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(IncidentType, on_delete=models.SET_NULL, null=True, blank=True)

    channel = models.ForeignKey(IncidentChannel, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    contact_email = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_incidents')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_incidents')
    
    # Termini: data límit, avisos enviats i pausa (estats que aturen el termini)
    due_at = models.DateTimeField(null=True, blank=True)
    warned_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    pause_warned_at = models.DateTimeField(null=True, blank=True)
    
    # Tramitació: primera resposta, tancament i com s'ha resolt
    first_response_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(null=True, blank=True)
    
    # Justificant de registre (art. 12)
    receipt_document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    receipt_sent_at = models.DateTimeField(null=True, blank=True)

    # Esborrat lògic
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"
        
    def __str__(self):
        return self.token if self.token else "Incident ID {}".format(self.id)

    @property
    def closed_on_time(self):
        """Si s'ha tancat dins de termini (None si no té termini o no està tancada)."""
        if not self.closed_at or not self.due_at:
            return None
        return self.closed_at <= self.due_at

    def delete(self, *args, **kwargs):
        # Dins del període de retenció no es pot esborrar físicament (només lògicament)
        from notification.utils.incident_utils import within_retention
        if within_retention(self):
            from django.core.exceptions import ValidationError
            raise ValidationError("Incident is within the retention period and cannot be deleted.")
        return super().delete(*args, **kwargs)

class IncidentReport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    incident_data = models.DateField(null=True, blank=True)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    description = models.TextField(null=True, blank=True)
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # Esborrat lògic, amb el justificant de qui l'ha esborrat i per què
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    deletion_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.token if self.token else "Incident Report ID {}".format(self.id)

class IncidentDocumentation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    incident_report = models.ForeignKey(IncidentReport, on_delete=models.CASCADE, related_name='documentation_files', null=True, blank=True) 
    file = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f"Documentation for {self.incident_report.token}"

class IncidentObservation(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(IncidentStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "IncidentObservation {}".format(self.id)