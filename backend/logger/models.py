from django.db import models
from django.contrib.auth.models import User
from billing.models import Invoice, InvoiceStatus, JoinedPayment, JoinedPaymentStatus, Payment, PaymentStatus
from claimrequest.models import ClaimRequest, ClaimRequestStatus
from billing.models import CommitmentDeposit, CommitmentDepositStatus, Invoice, InvoiceStatus, PaymentCommitment
from communication.models import Communication, CommunicationProcessStatus, CommunicationStatus, CommunicationProcess, MessageType
from contract.models import Bail, BailStatus, Bonification, Contract, ContractDebtManagement, ContractRequest, ContractRequestStatus, Variable
from fraud.models import Fraud, FraudStatus
from notification.models import Incident, IncidentStatus
from order.models import Order, OrderStatus
from pricing.models import LineItemType, Product, PriceRate
from service.models import Connection, ConnectionStatus, ConnectionRequest, ConnectionRequestStatus, Cluster, ClusterStatus, ClusterNozzle, ClusterNozzleStatus, SupplyPoint, SupplyCut, SupplyCutStatus

class LogConnectionStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Connection, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(ConnectionStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(ConnectionStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"


class LogConnectionRequestStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(ConnectionRequest, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(ConnectionRequestStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(ConnectionRequestStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"
    
class LogClusterStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Cluster, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(ClusterStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(ClusterStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogClusterNozzleStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(ClusterNozzle, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(ClusterNozzleStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(ClusterNozzleStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogSupplyCutStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(SupplyCut, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(SupplyCutStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(SupplyCutStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogSupplyPointChange(models.Model):
    ACTION_CHOICES = [
        ('activate', 'Activació'),
        ('deactivate', 'Baixa'),        
        ('meter', 'Canvi de comptador'),
        ('address', 'Canvi d\'adreça'),
        ('connection', 'Canvi d\'escomesa'),
        ('property', 'Canvi de propietat'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.SET_NULL, null=True, related_name='change_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    field_changed = models.CharField(max_length=50, null=True, blank=True)
    previous_value = models.TextField(null=True, blank=True)
    current_value = models.TextField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    previous_related_id = models.IntegerField(null=True, blank=True)
    current_related_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        user_str = self.user.username if self.user else 'Desconegut'
        return f"{self.timestamp} - {self.action} en {self.supply_point} per {user_str}"

class LogContractChange(models.Model):
    ACTION_CHOICES = [
        ('activate', 'Activació'),
        ('deactivate', 'Baixa'),        
        ('person', 'Canvi de persona'),
        ('address', 'Canvi d\'adreça'),
        ('communication_type', 'Canvi de tipus de comunicació')
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, related_name='change_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    field_changed = models.CharField(max_length=50, null=True, blank=True)
    previous_value = models.TextField(null=True, blank=True)
    current_value = models.TextField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    previous_related_id = models.IntegerField(null=True, blank=True)
    current_related_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        user_str = self.user.username if self.user else 'Desconegut'
        return f"{self.timestamp} - {self.action} en {self.supply_point} per {user_str}"


class LogContractRequestStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(ContractRequest, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(ContractRequestStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(ContractRequestStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"


class LogOrderStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(OrderStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(OrderStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogBailStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Bail, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(BailStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(BailStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogContractTotalMembers(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True)
    previous_total_persons = models.IntegerField(null=True, blank=True)
    current_total_persons = models.IntegerField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_total_persons} to {self.current_total_persons}"


class LogContractPhones(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True)
    previous_phone = models.TextField(null=True, blank=True)
    current_phone = models.TextField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - Phones {self.previous_phone} -> {self.current_phone}"


class LogContractBonificationsVariablesChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True)
    previous_bonification = models.ForeignKey(Bonification, on_delete=models.SET_NULL, null=True, related_name='log_previous_bonification')
    current_bonification = models.ForeignKey(Bonification, on_delete=models.SET_NULL, null=True, related_name='log_current_bonification')
    previous_variable = models.ForeignKey(Variable, on_delete=models.SET_NULL, null=True, related_name='log_previous_variable')
    current_variable = models.ForeignKey(Variable, on_delete=models.SET_NULL, null=True, related_name='log_current_variable')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_variable} to {self.current_variable}"

class LogContractExpiredBonificationsVariables(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True)
    expired_bonification = models.ForeignKey(Bonification, on_delete=models.SET_NULL, null=True, related_name='log_expired_bonification')
    expired_variable = models.ForeignKey(Variable, on_delete=models.SET_NULL, null=True, related_name='log_expired_bonification')
    expiring_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.timestamp} - Contract {self.object.token} with expired variables"
 
class LogClaimRequestContractChange(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    object = models.ForeignKey(ClaimRequest, on_delete=models.CASCADE, null=True, blank=True)
    deleted_contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True)
    current_debt_management = models.ForeignKey(ContractDebtManagement, on_delete=models.SET_NULL, null=True, blank=True)
    previous_status = models.ForeignKey(ClaimRequestStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='previous_status_logs')
    current_status = models.ForeignKey(ClaimRequestStatus, on_delete=models.SET_NULL, null=True, blank=True, related_name='current_status_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"Log Claim Request Contract Change {self.id}"
           
class LogInvoiceChangeStatus(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(InvoiceStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(InvoiceStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"
           
class LogCommitmentDepositMovement(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(CommitmentDeposit, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(CommitmentDepositStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(CommitmentDepositStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    new_payment = models.ForeignKey(PaymentCommitment, on_delete=models.SET_NULL, null=True, blank=True, related_name='log_new_payment')
    new_wallet = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='log_new_wallet')
    new_invoices = models.ManyToManyField(Invoice, blank=True, related_name='log_new_invoices')
    previous_remaining = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    current_remaining = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    used_remaining = models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True)
    paid_invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='log_paid_invoice')
    paid_invoice_payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='log_paid_payment')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogPaymentStatusChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(PaymentStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(PaymentStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    used_payment_token = models.CharField(max_length=255, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username if self.user else 'Unknown'}"

class LogFraudStatusChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Fraud, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(FraudStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(FraudStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogIncidentStatusChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Incident, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(IncidentStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(IncidentStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogCommunicationStatusChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Communication, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(CommunicationStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(CommunicationStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogCommunicationProcessStatusChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(CommunicationProcess, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(CommunicationProcessStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(CommunicationProcessStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogInvoiceDataChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True)
    previous_address = models.CharField(max_length=255, null=True, blank=True)
    current_address = models.CharField(max_length=255, null=True, blank=True)
    previous_payment_type = models.CharField(max_length=255, null=True, blank=True)
    current_payment_type = models.CharField(max_length=255, null=True, blank=True)
    previous_iban = models.CharField(max_length=255, null=True, blank=True)
    current_iban = models.CharField(max_length=255, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"


class LogReadingChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='reading_change_logs')
    meter = models.ForeignKey('service.Meter', on_delete=models.SET_NULL, null=True, blank=True, related_name='reading_change_logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reading_date = models.DateField(null=True, blank=True)
    previous_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)

    def __str__(self):
        user_str = self.user.username if self.user else 'Desconegut'
        return f"{self.timestamp} - Canvi de lectura en {self.meter} per {user_str}"

class LogJoinedPaymentStatusChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(JoinedPayment, on_delete=models.SET_NULL, null=True)
    previous_status = models.ForeignKey(JoinedPaymentStatus, on_delete=models.SET_NULL, null=True, related_name='log_previous_status')
    current_status = models.ForeignKey(JoinedPaymentStatus, on_delete=models.SET_NULL, null=True, related_name='log_current_status')
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.timestamp} - From {self.previous_status} to {self.current_status} by {self.user.username}"

class LogCommunicationChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Communication, on_delete=models.SET_NULL, null=True)
    previous_types = models.ManyToManyField(MessageType, blank=True, related_name='log_previous_use_types')
    current_types = models.ManyToManyField(MessageType, blank=True, related_name='log_current_use_types')
    previous_used_email = models.CharField(max_length=255, null=True, blank=True)
    current_used_email = models.CharField(max_length=255, null=True, blank=True)
    previous_used_phone = models.CharField(max_length=255, null=True, blank=True)
    current_used_phone = models.CharField(max_length=255, null=True, blank=True)
    previous_used_address = models.CharField(max_length=255, null=True, blank=True)
    current_used_address = models.CharField(max_length=255, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.timestamp} - From {self.previous_types} to {self.current_types} by {self.user.username}"
    
class LogProductChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    changed_field = models.CharField(max_length=255, null=True, blank=True)
    previous_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.timestamp} - {self.changed_field} from {self.previous_value} to {self.new_value} by {self.user.username}"
    
class LogPriceRateChange(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    object = models.ForeignKey(PriceRate, on_delete=models.SET_NULL, null=True)
    line_item_type_name = models.CharField(max_length=255, null=True, blank=True)
    changed_field = models.CharField(max_length=255, null=True, blank=True)
    previous_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return f"{self.timestamp} - {self.changed_field} from {self.previous_value} to {self.new_value} by {self.user.username}"
    
