from django.conf import settings
from django.db import models
from pydantic import ValidationError

class Document(models.Model):
    date = models.DateField(null=True, blank=True)
    entity = models.CharField(max_length=255, null=True, blank=True)
    field = models.CharField(max_length=255, null=True, blank=True)
    entity_id = models.IntegerField()
    entity_token = models.CharField(max_length=255, null=True, blank=True)
    
    file = models.FileField(null=True, blank=True, storage=None)
    folder = models.CharField(max_length=255, null=True, blank=True)
    document_name = models.CharField(max_length=255, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    location_url = models.URLField(null=True, blank=True)
    
    version = models.IntegerField(default=1)
    parent_document = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='versions')
    
    SERVICE_CHOICES = [
        ('hdd', 'HDD'),
        ('azure', 'Azure'),
        ('cloud', 'Cloud'),
        ('ftp', 'FTP'),
        ('aws', 'AWS'),
        ('alfresco', 'Alfresco'),
    ]
    service = models.CharField(max_length=50, choices=SERVICE_CHOICES)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        supported_services = ['hdd', 'ftp', 'aws', 'alfresco', 'azure', 'cloud']
        if self.service not in supported_services:
            raise ValidationError(f"Unsupported service: {self.service}")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.document_name


class DocumentSign(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)

    contract = models.ForeignKey('contract.Contract', on_delete=models.SET_NULL, null=True, blank=True, related_name='document_signs')
    contract_request = models.ForeignKey('contract.ContractRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='document_signs')

    contract_file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='document_signs_as_file')
    contract_file_signed = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='document_signs_as_signed_file')
    signed_at = models.DateTimeField(null=True, blank=True)

    STATUS_PENDING = 1
    STATUS_SENDED = 2
    STATUS_SIGNED = 3
    STATUS_EXPIRED = 4
    STATUS_ERROR = -1

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENDED, 'Sended'),
        (STATUS_SIGNED, 'Signed'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_ERROR, 'Error'),
    ]
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_report = models.CharField(max_length=255, null=True, blank=True)

    otp_name = models.CharField(max_length=255, null=True, blank=True)
    otp_email = models.EmailField(null=True, blank=True)
    otp_phone = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = "Document Sign"
        verbose_name_plural = "Document Signs"

    def __str__(self):
        return self.token if self.token else "DocumentSign ID {}".format(self.id)


class ExportJob(models.Model):
    """
    Cua general de descàrregues: una fila per cada fitxer que un usuari demana
    generar en segon pla (exportacions de llistats, CSV, informes...).

    Existeix perquè el frontal pugui recuperar el fitxer encara que l'usuari
    hagi marxat de la pàgina o refrescat: abans el `task_id` només vivia al
    component i el `document_id` només al resultat de Celery (que s'esborra).

    La fila la crea `enqueue_export()` (documentmanager/utils/export_jobs.py) abans
    de despatxar la tasca, i l'actualitzen els signals de Celery
    (documentmanager/signals.py), de manera que les tasques no s'han de modificar:
    n'hi ha prou que retornin `{"document_id", "document_name"}` o `{"file_url"}`,
    i `{"status": "error", "message"}` quan fallen.
    """

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    ACTIVE_STATUSES = (STATUS_PENDING, STATUS_RUNNING)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="export_jobs",
    )
    # Identificador estable del tipus d'exportació (p. ex. "generic:invoice", "readings").
    kind = models.CharField(max_length=100)
    # Nom visible al panell de descàrregues.
    name = models.CharField(max_length=255)
    # Paràmetres amb què s'ha demanat (filtres, columnes...), per mostrar-los i poder-la repetir.
    params = models.JSONField(default=dict, blank=True)

    task_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    error_message = models.TextField(null=True, blank=True)

    # Resultat: un Document del gestor documental o, per a tasques que encara
    # escriuen a `tmp/`, la URL del fitxer temporal.
    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    file_url = models.TextField(null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # L'usuari l'ha tret del panell; la fila es conserva fins a la neteja periòdica.
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["requested_by", "-created_at"], name="documentman_request_ae1e28_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.status})"

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES
