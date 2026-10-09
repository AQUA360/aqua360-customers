from django.db import models
from django.contrib.auth.models import User

from billing.models import CommitmentDeposit, Invoice
from contract.models import Contract
from documentmanager.models import Document
from order.models import Order
from service.models import Cluster, SupplyPoint


class IncidentStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "IncidentStatus ID {}".format(self.token)
    
class IncidentType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    
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


class CalendarTask(models.Model):
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
    
    set_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Calendar Task"
        verbose_name_plural = "Calendar Tasks"
        
    def __str__(self):
        return self.name if self.name else "Calendar Task ID {}".format(self.id)
    

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
    tasks = models.ManyToManyField(CalendarTask, blank=True, related_name='incidents')
    
    status = models.ForeignKey(IncidentStatus, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(IncidentType, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Incident"
        verbose_name_plural = "Incidents"
        
    def __str__(self):
        return self.token if self.token else "Incident ID {}".format(self.id)

class IncidentReport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    incident_data = models.DateField(null=True, blank=True)
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    description = models.TextField(null=True, blank=True)
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
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