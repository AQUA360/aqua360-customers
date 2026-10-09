from django.db import models
from django.contrib.auth.models import User

from contract.models import Contract
from coredata.models import Person, PersonAddress
from documentmanager.models import Document
from service.models import CompanyConfig, CompanyConfigEmail

class MessageType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name if self.name else "MessageType ID {}".format(self.token)

class MessageOrigin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name if self.name else "MessageOrigin ID {}".format(self.token)

class CommunicationStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name if self.name else "CommunicationStatus ID {}".format(self.token)

class CommunicationUseType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name if self.name else "CommunicationStatus ID {}".format(self.token)

class CommunicationProcessStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name if self.name else "CommunicationProcessStatus ID {}".format(self.token)


class MessageTypeTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    type = models.ForeignKey(MessageType, on_delete=models.CASCADE, null=True, blank=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    body = models.TextField(null=True, blank=True)
    document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    
    unused = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.token if self.token else "MessageTypeTemplate ID {}".format(self.id)
    
class MessageTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    name = models.CharField(max_length=255, null=True, blank=True)
    
    origin = models.ForeignKey(MessageOrigin, on_delete=models.SET_NULL, null=True, blank=True)
    templates = models.ManyToManyField(MessageTypeTemplate, blank=True, related_name='message_templates')
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name if self.name else "MessageTemplate ID {}".format(self.token)

class Message(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    subject = models.CharField(max_length=255, null=True, blank=True)
    body = models.TextField(null=True, blank=True)
    type = models.ForeignKey(MessageType, on_delete=models.SET_NULL, null=True, blank=True)
    
    message_date = models.DateField(null=True, blank=True)
    message_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.token if self.token else f"Message ID {self.id}"
    
    
class CommunicationProcess(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    description = models.TextField(null=True, blank=True)
    status = models.ForeignKey(CommunicationProcessStatus, on_delete=models.SET_NULL, null=True, blank=True)
    use_type = models.ForeignKey(CommunicationUseType, on_delete=models.SET_NULL, null=True, blank=True)
    
    used_types = models.ManyToManyField(MessageTypeTemplate, blank=True, related_name='communication_processes_used_types')
    type_tokens = models.CharField(max_length=255, null=True, blank=True)
    type_names = models.CharField(max_length=255, null=True, blank=True)
    template = models.ForeignKey(MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    messages = models.ManyToManyField(Message, blank=True, related_name='communication_processes')
    
    readings = models.ManyToManyField('billing.Reading', blank=True, related_name='communication_processes')
    # FUTURE POSSIBLE RELATED DATA OBJECTS
    
    # Supply cuts this process was created for. Populated from the cut menu, the
    # supply cut management option and the step 1 supply cut filter, so every
    # entry path records the origin. Used to warn (and, while another process is
    # in flight, to block) when a second process is started for the same cut.
    supply_cuts = models.ManyToManyField(
        'service.SupplyCut', blank=True, related_name='communication_processes'
    )
    # Identifies one logical wizard run so the batches of a batched save ignore
    # each other while still blocking a different user's run.
    run_token = models.CharField(max_length=64, null=True, blank=True)
    
    separate_communications = models.BooleanField(default=False)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    updating_messages_task_id = models.CharField(max_length=255, null=True, blank=True)
    
    download_letters_task_id = models.CharField(max_length=255, null=True, blank=True)
    download_einvoices_task_id = models.CharField(max_length=255, null=True, blank=True)
    
    due_date = models.DateField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.token if self.token else "CommunicationProcess ID {}".format(self.token)

class Communication(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    status = models.ForeignKey(CommunicationStatus, on_delete=models.SET_NULL, null=True, blank=True)
    use_type = models.ForeignKey(CommunicationUseType, on_delete=models.SET_NULL, null=True, blank=True)
    
    process = models.ForeignKey(CommunicationProcess, on_delete=models.SET_NULL, null=True, blank=True, related_name='communications')
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='communications')
    contracts = models.ManyToManyField(Contract, blank=True, related_name='communications')
    company_config = models.ForeignKey(CompanyConfig, on_delete=models.SET_NULL, null=True, blank=True, related_name='communications_config')   #dades remitent
    company_config_email = models.ForeignKey(CompanyConfigEmail, on_delete=models.SET_NULL, null=True, blank=True, related_name='communications_config_email')
    
    used_phones = models.CharField(max_length=255, null=True, blank=True) 
    used_email = models.EmailField(null=True, blank=True)
    address = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True)
    used_address = models.CharField(max_length=255, null=True, blank=True) 
    preferred_communication_type = models.CharField(max_length=255, null=True, blank=True)  #WHEN SAVING WITH DEFAULT TYPE, SAVE THIS CONTRACT VALUE IF IT EXISTS
    
    accounting_office = models.CharField(max_length=255, null=True, blank=True)
    managing_body = models.CharField(max_length=255, null=True, blank=True)
    processing_unit = models.CharField(max_length=255, null=True, blank=True)
    
    messages = models.ManyToManyField(Message, blank=True, related_name='communications')
    email_html_content = models.TextField(null=True, blank=True)  # pre-rendered HTML email
    types = models.ManyToManyField(MessageType, blank=True, related_name='communications')
    type_tokens = models.CharField(max_length=255, null=True, blank=True)
    type_names = models.CharField(max_length=255, null=True, blank=True)
    
    #extra documents (relations) to attach to communication
    invoices = models.ManyToManyField('billing.Invoice', blank=True, related_name='communications')
    readings = models.ManyToManyField('billing.Reading', blank=True, related_name='communications')
    
    always_attach = models.BooleanField(default=False)
    due_date = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    rejection_reason = models.TextField(null=True, blank=True)
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Communication"
        verbose_name_plural = "Communications"
    
    def __str__(self):
        return self.token if self.token else f"Communication ID {self.id}"

class CommunicationFile(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    is_letter = models.BooleanField(default=False)
    invoice = models.ForeignKey('billing.Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    
    communication = models.ForeignKey(Communication, on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    is_active = models.BooleanField(default=True)
    # Permet generar i arxivar un document vinculat a la comunicació sense que viatgi com
    # a adjunt del correu. `True` per defecte, per mantenir el comportament de tots els
    # fitxers ja existents. El frontend no llista al tab de documents els que el tenen a
    # `False`, per no fer pensar que s'enviaran.
    attach_to_email = models.BooleanField(default=True)
    # El mateix per al canal postal: el document es genera i s'arxiva igualment, pero no
    # entra al paquet de documents que es descarrega per enviar per carta.
    attach_to_letter = models.BooleanField(default=True)
    
    def __str__(self):
        return self.token if self.token else f"CommunicationFile ID {self.id}"

class CommunicationProcessObservation(models.Model):
    process = models.ForeignKey(CommunicationProcess, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(CommunicationProcessStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "CommunicationProcessObservation {}".format(self.id)

class CommunicationObservation(models.Model):
    communication = models.ForeignKey(Communication, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(CommunicationStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "CommunicationObservation {}".format(self.id)