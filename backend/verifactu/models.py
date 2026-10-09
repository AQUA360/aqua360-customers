from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class VerifactuBatch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    action = models.CharField(max_length=255, null=True, blank=True)
    response_status = models.CharField(max_length=255, null=True, blank=True)
    response = models.CharField(null=True, blank=True)
    
    def __str__(self):
        return self.token if self.token else "VerifactuBatch ID {}".format(self.id)
    
class VerifactuNotification(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    # invoice = models.ForeignKey('billing.Invoice', on_delete=models.SET_NULL, null=True, blank=True)
    batch = models.ForeignKey(VerifactuBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="verifactu_notifications")
    response_status = models.CharField(max_length=255, null=True, blank=True)
    
    message = models.CharField(null=True, blank=True)
    
    verifactu_hash = models.CharField(max_length=255, null=True, blank=True)
    verifactu_qr = models.CharField(max_length=255, null=True, blank=True)
    
    message_type = models.CharField(max_length=255, null=True, blank=True)
    
    hash_IDEmisor = models.CharField(max_length=255, null=True, blank=True)
    hash_NumSerie = models.CharField(max_length=255, null=True, blank=True)
    hash_FechaExpedicion = models.CharField(max_length=255, null=True, blank=True)
    hash_TipoFactura = models.CharField(max_length=255, null=True, blank=True)
    hash_CuotaTotal = models.CharField(max_length=255, null=True, blank=True)
    hash_ImporteTotal = models.CharField(max_length=255, null=True, blank=True)
    hash_Huella = models.CharField(max_length=255, null=True, blank=True)
    hash_FechaHoraHusoGenRegistro = models.CharField(max_length=255, null=True, blank=True)
    
    cancelled_notification = models.ForeignKey('verifactu.VerifactuNotification', on_delete=models.SET_NULL, null=True, blank=True, related_name="cancelling_notification")
    
    verifactu_previous_notification = models.ForeignKey('verifactu.VerifactuNotification', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return self.token if self.token else "VerifactuNotification ID {}".format(self.id)


class VerifactuNotificationLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    verifactu_notification = models.ForeignKey(VerifactuNotification, on_delete=models.CASCADE, related_name='verifactu_notification_logs')
    field_name = models.TextField(null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    operation_token = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Prevent updates - only allow creation
        if self.pk:
            raise ValueError("VerifactuNotificationLog entries cannot be modified. They are create-only.")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Prevent deletion
        raise ValueError("VerifactuNotificationLog entries cannot be deleted. They are create-only.")
    
    def __str__(self):
        return f'VerifactuNotificationLog {self.id}'