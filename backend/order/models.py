# order/models.py
from django.db import models
from documentmanager.models import Document
from lecturapp.models import ReadingOperator
from service.models import ConnectionRequest, SupplyPoint, Connection
from coredata.models import Address, Person
from django.contrib.auth.models import User
from django.conf import settings

class OrderType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    gmao_department_token = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name if self.name else "OrderType ID {}".format(self.token)

class OrderReason(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    type = models.ManyToManyField(OrderType, related_name='reasons', blank=True)
    
    def __str__(self):
        return self.name if self.name else "OrderReason ID {}".format(self.token)

class OrderStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "OrderStatus ID {}".format(self.token)


class Operator(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    surname = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_team = models.BooleanField(default=False)
    description = models.JSONField(null=True, blank=True)
    
    app_user = models.ForeignKey(ReadingOperator, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Operator"
        verbose_name_plural = "Operators"

    def __str__(self):
        return self.token if self.token else "Operator ID {}".format(self.id)
    
class OrderPriority(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "OrderPriority ID {}".format(self.token)
    

class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True, unique=True)
    order_file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)

    
    def _get_contract_model(self):
        from contract.models import Contract
        return Contract
    
    def _get_contract_request_model(self):
        from contract.models import ContractRequest
        return ContractRequest
    
    contract = models.ForeignKey('contract.Contract', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    contract_request = models.ForeignKey('contract.ContractRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    contract_termination_request = models.ForeignKey('contract.ContractTerminationRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.SET_NULL, null=True, blank=True)
    connection = models.ForeignKey(Connection, on_delete=models.SET_NULL, null=True, blank=True)
    connection_request = models.ForeignKey(ConnectionRequest, on_delete=models.SET_NULL, null=True, blank=True)
    claim_request = models.ForeignKey('claimrequest.ClaimRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    incident = models.ForeignKey('notification.Incident', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    
    dueDateAt = models.DateField(null=True, blank=True)
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    operators = models.ManyToManyField(Operator, related_name='orders', blank=True)

    change_meter_applied_at = models.DateTimeField(null=True, blank=True)
    change_meter_applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    
    type = models.ForeignKey(OrderType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Order Type")
    reason = models.ForeignKey(OrderReason, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Order Reason")
    status = models.ForeignKey(OrderStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Order Status")
    priority = models.ForeignKey(OrderPriority, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Order Priority")
    
    description = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=17, decimal_places=14, null=True, blank=True)
    longitude = models.DecimalField(max_digits=17, decimal_places=14, null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    is_active = models.BooleanField(default=True)
        
    class Meta:
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return self.token if self.token else "Order ID {}".format(self.id)



  
class OrderReport(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='reports', null=True, blank=True)
    operator = models.ForeignKey(Operator, on_delete=models.SET_NULL, null=True, blank=True)
    start_at = models.TimeField(null=True, blank=True)
    end_at = models.TimeField(null=True, blank=True)
    time_dedicated = models.IntegerField(null=True, blank=True)
    report_date = models.DateField(null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return self.token if self.token else "Order Report ID {}".format(self.id)
    
class OrderReportDocument(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    order_report = models.ForeignKey(OrderReport, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    
    def __str__(self):
        return self.token if self.token else "Order Report Document ID {}".format(self.id)

class OrderObservation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    operator = models.ForeignKey(Operator, on_delete=models.SET_NULL, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(OrderStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return self.observation if self.observation else "Order Observation ID {}".format(self.id)