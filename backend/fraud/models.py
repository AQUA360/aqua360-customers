from django.db import models

from django.contrib.auth.models import User

from contract.models import Contract
from documentmanager.models import Document
from service.models import SupplyPoint

class FraudStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "FraudStatus ID {}".format(self.token)

class FraudType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "FraudType ID {}".format(self.token)
    
class Fraud(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    detection_date = models.DateField(null=True, blank=True)
    
    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.SET_NULL, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True)
    
    status = models.ForeignKey(FraudStatus, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(FraudType, on_delete=models.SET_NULL, null=True, blank=True)
    class Meta:
        verbose_name = "Fraud"
        verbose_name_plural = "Frauds"
    
    def __str__(self):
        return f"Fraud {self.token}"

class FraudReport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    report_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    fraud = models.ForeignKey(Fraud, on_delete=models.CASCADE, related_name='reports', null=True, blank=True)
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f"Fraud Report {self.token}"

class FraudObservation(models.Model):
    fraud = models.ForeignKey(Fraud, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(FraudStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "SupplyPointObservation {}".format(self.id)

class FraudDocumentation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    fraud_report = models.ForeignKey(FraudReport, on_delete=models.CASCADE, related_name='documentation_files', null=True, blank=True) 
    #type?
    file = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Documentation for {self.fraud_report.token}"

class FraudImage(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    fraud_report = models.ForeignKey(FraudReport, on_delete=models.CASCADE, related_name='image_files', null=True, blank=True) 
    file = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Image for {self.fraud_report.token}"