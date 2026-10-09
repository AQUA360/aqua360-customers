from django.db import models
from billing.models import Invoice, Payment, PaymentStatus
from contract.models import BonificationType, Contract, ContractClientType, ContractDebtManagement, ContractRequest, ContractStatus, ContractUseType, VariableType
from service.models import Exploitation, RouteZone
from coredata.models import Person
from django.contrib.auth.models import User
from documentmanager.models import Document

class VulnerabilityRequestStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False) 
    
    def __str__(self):
        return self.name if self.name else "VulnerabilityRequestStatus ID {}".format(self.token)

class VulnerabilityRequestType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    bonification_types = models.ManyToManyField(BonificationType, related_name='vulnerability_request_types', blank=True)
    variable_types = models.ManyToManyField(VariableType, related_name='vulnerability_request_types', blank=True)
    duration = models.IntegerField(null=True, blank=True) # DIES O TEMPS FINS QUE EXPIRA
    vulnerability_level = models.IntegerField(null=True, blank=True) # 0: No vulnerable, 1: En Risc, 2: Vulnerable
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}" if self.name else "Template ID {}".format(self.id)

class ClaimRequestTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name}" if self.name else "Template ID {}".format(self.id)


class ClaimRequestStepTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    template = models.ForeignKey(ClaimRequestTemplate, on_delete=models.CASCADE, related_name='steps')
    
    duration = models.IntegerField(null=True, blank=True)
    TYPE_CHOICES = [
        ('WORK', 'Hábils'),
        ('NATURAL', 'Naturals'),
    ]
    duration_type = models.CharField(max_length=255, choices=TYPE_CHOICES, null=True, blank=True, default='WORK')
    
    document_type = models.ForeignKey('ClaimDocumentType', on_delete=models.SET_NULL, null=True, blank=True)
    order_type = models.ForeignKey('order.OrderType', on_delete=models.SET_NULL, null=True, blank=True)
    next_step = models.ForeignKey('ClaimRequestStepTemplate', on_delete=models.SET_NULL, null=True, blank=True)
    price_rates = models.ManyToManyField('pricing.PriceRate', related_name='claim_request_step_templates', blank=True)
    
    
    PRICE_RATE_BILLING_TYPE_CHOICES = [
        ('contract', 'Contract'),
        ('invoice', 'Invoice'),
    ]
    billing_type = models.CharField(max_length=255, choices=PRICE_RATE_BILLING_TYPE_CHOICES, null=True, blank=True, default='invoice')
    group_payments = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name}" if self.name else "Step Template ID {}".format(self.id)


class ClaimRequestStep(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    claim_request = models.ForeignKey('ClaimRequest', on_delete=models.CASCADE, related_name='steps')
    step_template = models.ForeignKey(ClaimRequestStepTemplate, on_delete=models.SET_NULL, null=True)
    
    # Camps copiats de ClaimRequestStepTemplate
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)
    TYPE_CHOICES = [
        ('WORK', 'Hábils'),
        ('NATURAL', 'Naturals'),
    ]
    duration_type = models.CharField(max_length=255, choices=TYPE_CHOICES, null=True, blank=True, default='WORK')
    action_date_at = models.DateField(null=True, blank=True)
    document_type = models.ForeignKey('ClaimDocumentType', on_delete=models.SET_NULL, null=True, blank=True)
    order_type = models.ForeignKey('order.OrderType', on_delete=models.SET_NULL, null=True, blank=True)
    next_step = models.ForeignKey('ClaimRequestStep', on_delete=models.SET_NULL, null=True, blank=True)
    
    communication_process = models.ForeignKey('communication.CommunicationProcess', on_delete=models.SET_NULL, null=True, blank=True)
    price_rates = models.ManyToManyField('pricing.PriceRate', related_name='claim_request_steps', blank=True)
    
    # Camps específics de ClaimRequestStep
    is_completed = models.BooleanField(default=False)
    end_step_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    task_id = models.CharField(max_length=255, null=True, blank=True)
    
    
    def __str__(self):
        return f"Step {self.position} for Claim {self.claim_request.token}"

class ClaimRequestStepDocument(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    claim_request_step = models.ForeignKey(ClaimRequestStep, on_delete=models.CASCADE, related_name='documents')
    file = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='claim_request_step_documents')
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Document {self.document.name} for Step {self.claim_request_step.position}"

class ClaimRequestStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ClaimRequestStatus ID {}".format(self.token)


class ClaimDocumentType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ClaimDocumentType ID {}".format(self.token)


class ClaimRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    status = models.ForeignKey(ClaimRequestStatus, on_delete=models.SET_NULL, null=True, blank=True)
    template = models.ForeignKey(ClaimRequestTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    current_step = models.ForeignKey(ClaimRequestStep, on_delete=models.SET_NULL, null=True, blank=True, related_name='current_claim_requests')
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Claim Request"
        verbose_name_plural = "Claim Requests"
        
    def __str__(self):
        return f"Claim Request {self.token}"


class ClaimRequestPayment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    claim_request = models.ForeignKey(ClaimRequest, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='claim_requests')
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='claim_requests')
    is_paid = models.BooleanField(default=False)
    is_excluded = models.BooleanField(default=False)
    is_vulnerable = models.BooleanField(default=False)
    
    claim_step = models.ForeignKey(ClaimRequestStep, on_delete=models.SET_NULL, null=True, blank=True, related_name='claim_request_payments')
        
    def __str__(self):
        return f"Claim Request Invoice {self.token}"


class VulnerabilityRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    request_at = models.DateField(null=True, blank=True)
    start_at = models.DateField(null=True, blank=True)
    end_at = models.DateField(null=True, blank=True)
    
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='vulnerability_requests')
    contract_request = models.ForeignKey(ContractRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='vulnerability_requests')
    
    type = models.ForeignKey(VulnerabilityRequestType, on_delete=models.SET_NULL, null=True, blank=True, related_name='vulnerability_requests')
    status = models.ForeignKey(VulnerabilityRequestStatus, on_delete=models.SET_NULL, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='vulnerability_requests')
    claim_request = models.ForeignKey(ClaimRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='vulnerability_requests')
    
    is_active = models.BooleanField(default=True)   
    
    class Meta:
        verbose_name = "Vulnerability Request"
        verbose_name_plural = "Vulnerability Requests"
        
    def __str__(self):
        return f"Vulnerability Request {self.token}"

class VulnerabilityRequestDocumentation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    vulnerability_request = models.ForeignKey(VulnerabilityRequest, on_delete=models.SET_NULL, related_name='documentation_files', null=True, blank=True)
    #   type needed?
    file = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return f"Documentation for {self.vulnerability_request.token}"

class VulnerabilityRequestObservation(models.Model):
    vulnerability_request = models.ForeignKey(VulnerabilityRequest, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "CommitmentDepositObservation {}".format(self.id)