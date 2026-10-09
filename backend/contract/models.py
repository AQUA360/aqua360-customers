# contract/models.py

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from coredata.models import Person, PersonAddress, PersonCNAE, PersonBank, PersonContact
from documentmanager.models import Document
from service.models import Company, Exploitation, SupplyPoint
from order.models import OrderType, Order
from django.contrib.auth.models import User

#Contract
class ContractStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ContractStatus ID {}".format(self.token)

class ContractUseType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ContractUseType ID {}".format(self.token)
    
class ContractClientType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ContractClientType ID {}".format(self.token)

class ContractCategory(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ContractCategory ID {}".format(self.token)

class ContractDebtManagement(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name if self.name else "ContractDebtManagement ID {}".format(self.token)

#Contract Request
class ContractRequestStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ContractRequestStatus ID {}".format(self.token)


class ContractRequestDocumentationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    list_name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_mandatory = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    contract_request_type = models.ForeignKey('ContractRequestType', on_delete=models.CASCADE, null=True, blank=True, related_name='documentation_types')    
    
    def __str__(self):
        return self.name if self.name else "ContractRequestDocumentationType ID {}".format(self.token)

class ContractDocumentationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name if self.name else "ContractDocumentationType ID {}".format(self.token)


#Bail
class BailType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    default_import = models.FloatField(null=True, blank=True, default=50)
    
    def __str__(self):
        return self.name if self.name else "BailType ID {}".format(self.token)
    
class BailStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "BailStatus ID {}".format(self.token)

#Payment
class PaymentType(models.Model):
    TYPE_CHOICES = [
        ('CASH', 'Efectiu'),
        ('BANK_TRANSFER', 'Transferència bancària'),
        ('DIRECT_DEBIT', 'Domiciliació bancària (SEPA)'),
        ('CARD', 'Targeta (TPV Físic)'),
        ('BARCODE', 'Pagament bancari (Codi de barres)'),
        ('TPVV', 'TPV Virtual'),
        ('BALANCE', 'Saldo')
    ]
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(choices=TYPE_CHOICES, default='DIRECT_DEBIT')
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "PaymentType ID {}".format(self.token)

#Surrogation

class ContractSurrogationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name if self.name else "ContractSurrogationType ID {}".format(self.token)

#Termination

class ContractTerminationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name if self.name else "ContractTerminationType ID {}".format(self.token)

class ContractTerminationStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ContractTerminationStatus ID {}".format(self.token)


#Bonification Request

class BonificationTypeDocumentationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_mandatory = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    bonification_type = models.ForeignKey('BonificationType', on_delete=models.CASCADE, null=True, blank=True, related_name='bonification_type_documentation_types')
    
    def __str__(self):
        return self.name if self.name else "BonificationTypeDocumentationType ID {}".format(self.token)
      
      
#Contract Representative
class ContractRepresentativeType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "RepresentativeType ID {}".format(self.token)
 
class VariableType(models.Model):
    TYPE_CHOICES = [
        ('bool', 'Boolean'),
        ('int', 'Integer'),
        ('char', 'Character'),
        ('float', 'Float'),
        ('date', 'Date'),
        ('datetime', 'Datetime'),
    ]
    APPLICATION_CHOICES = [
        ('CT', 'Contract'),
        ('SP', 'SupplyPoint'),
        ('C', 'Cycle')
    ]
    
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    data_type = models.CharField(choices=TYPE_CHOICES, default='char')
    application = models.CharField(choices=APPLICATION_CHOICES, default='CT')
    is_vulnerable = models.BooleanField(default=False)
    position = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name


class Variable(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    type = models.ForeignKey(VariableType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Variable Type")

    # Valors
    value = models.CharField(max_length=255, null=True, blank=True)
    start_at = models.DateField(null=True, blank=True)
    end_at = models.DateField(null=True, blank=True)

    # relacions
    contract = models.ForeignKey('Contract', on_delete=models.SET_NULL, null=True, blank=True, related_name='variables')
    contract_request = models.ForeignKey('ContractRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='variables')
    bonification = models.ForeignKey('Bonification', on_delete=models.SET_NULL, null=True, blank=True, related_name='variables')
    
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name if self.name else "Variable ID {}".format(self.token)

class BonificationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    start_at = models.DateField(null=True, blank=True)
    end_at = models.DateField(null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    variable_types = models.ManyToManyField(VariableType, related_name="variable_types", blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name if self.name else "BonificationType ID {}".format(self.token)

    
class ContractRequestType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    exploitation = models.ForeignKey(Exploitation, on_delete=models.SET_NULL, null=True, blank=True)
    variable_types = models.ManyToManyField(VariableType, related_name="bonification_types", blank=True)
    order_types = models.ManyToManyField(OrderType,  blank=True, verbose_name="Contract Request Order Type")
    clause_templates = models.ManyToManyField('ClauseTemplate', blank=True, verbose_name="Clause Template")
    price_rates = models.ManyToManyField('pricing.PriceRate', blank=True, related_name="contract_request_type_price_rates", verbose_name="Price Rate")
    registration_price_rates = models.ManyToManyField('pricing.PriceRate', blank=True, related_name="contract_request_type_registration_price_rates", verbose_name="Registration Price Rate")
    has_persons = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    def __str__(self):
        return self.name if self.name else "ContractRequestType ID {}".format(self.token)

class Bail(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    contract = models.ForeignKey("contract.Contract", on_delete=models.CASCADE, related_name="bails_contract", null=True, blank=True)
    status = models.ForeignKey(BailStatus, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey("pricing.Product", on_delete=models.SET_NULL, null=True, blank=True)
    price_rate = models.ForeignKey("pricing.PriceRate", on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    invoice = models.ForeignKey("billing.Invoice", on_delete=models.SET_NULL, null=True, blank=True)
    return_date = models.DateField(null=True, blank=True)
    return_invoice_id = models.IntegerField(null=True, blank=True)
    is_billing = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Bail"
        verbose_name_plural = "Bails"
    
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Bail ID {}".format(self.id)

class ContractPayment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Payment Type")
    IBAN = models.ForeignKey(PersonBank, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Payment Bank")
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "ContractPayment ID {}".format(self.id)

class ContractPriceRate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.CASCADE, null=True, blank=True, related_name='contracts_price_rates')
    price_rate = models.ForeignKey('pricing.PriceRate', on_delete=models.CASCADE, null=True, blank=True, related_name='contracts_price_rates')
    is_active = models.BooleanField(default=True)
    is_bop_reference = models.BooleanField(default=False, verbose_name="Referència per a tarifa BOP")
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "ContractPriceRate ID {}".format(self.id)

def documentation_upload_to(instance, filename):
    return f'uploads/contracts/documentation/{instance.id}/{filename}'

def contract_upload_to(instance, filename):
    return f'uploads/contract/contracts/{instance.id}/{filename}'

class PiggyBank(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='piggy_banks')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f'PiggyBank {self.token}'

class PiggyBankMovement(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    movement_date = models.DateField(null=True, blank=True)
    
    piggy_bank = models.ForeignKey(PiggyBank, on_delete=models.CASCADE, related_name='movements')
    payment = models.ForeignKey('billing.Payment', null=True, blank=True, on_delete=models.CASCADE, related_name='piggy_bank_movements')
    bail = models.ForeignKey(Bail, on_delete=models.CASCADE, related_name='piggy_bank_movements', null=True, blank=True)
    commitment_deposit = models.ForeignKey('billing.CommitmentDeposit', on_delete=models.CASCADE, related_name='piggy_bank_movements', null=True, blank=True)
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='piggy_bank_movements') # USER WHEN REMOVING OR ADDING MANUAL MOVEMENTS
    
    is_positive = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)


class GeneralInvoice(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    payment = models.ForeignKey('billing.GeneralPayment', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="General Payment")
    address_billing = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Address Billing", related_name="general_invoices_billing")
    address_contact = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Address Contact", related_name="general_invoices_contact")
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f'GeneralInvoice {self.token} '

class Contract(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    language = models.CharField(max_length=2, choices=settings.LANGUAGES, default=settings.LANGUAGE)

    user_pinned = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pinned_contracts')
    user_checked = models.ManyToManyField(User, blank=True, related_name='checked_contracts')
    
    supply_point_default = models.ForeignKey(SupplyPoint, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract SupplyPoint", related_name="default_contracts")
    supply_points = models.ManyToManyField(SupplyPoint, blank=True, related_name="contracts")
    
    # Persons
    owner = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Owner", related_name="contracts_owner")
    tenant = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Tenant", related_name="contracts_tenant")
    holder = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True,verbose_name="Contract Holder", related_name='contracts_holder')
    total_persons = models.IntegerField(default=3, validators=[MinValueValidator(1)])
    
    address_billing = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Billing Address", related_name="contracts_billing")
    address_contact = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Contact Address", related_name="contracts_contact")

    payment = models.ForeignKey('billing.GeneralPayment', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Payment")
    cnaes = models.ManyToManyField(PersonCNAE, related_name='contracts', blank=True)
    
    contract_request = models.ForeignKey('ContractRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='contract')
    contract_request_type = models.ForeignKey(ContractRequestType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Request Type")
    
    status = models.ForeignKey(ContractStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Status")
    use_type = models.ForeignKey(ContractUseType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Use Type", related_name='contracts')
    client_type = models.ForeignKey(ContractClientType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Client Type")
    category = models.ForeignKey(ContractCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Category")
    USE_ACA_CHOICES = [
        ('Q', 'USOS RAMADERS SENSE CÀNON'),
        ('D', 'DOMÈSTICS'),
        ('I', 'INDUSTRIALS'),
        ('A', 'MUNICIPAL'),
        ('E', 'EXEMPTS'),
        ('M', 'MÈSURES DIRECTES')
    ]
    use_aca = models.CharField(max_length=10, choices=USE_ACA_CHOICES, default=None, null=True, blank=True)
    
    use_general_price_rates = models.BooleanField(default=False)
    price_rates = models.ManyToManyField(ContractPriceRate, related_name='contracts_price_rates', blank=True)
    registration_price_rates = models.ManyToManyField('pricing.PriceRate', related_name='contracts_registration_price_rates', blank=True)
    contacts = models.ManyToManyField(PersonContact, related_name='contract_contacts', blank=True)
    COMMUNICATION_CHOICES = [
        ('PAPER', 'Paper'),
        ('PHYSICAL', 'Física'),
        ('DIGITAL', 'Digital'),
        ('BOTH', 'Ambdues'),
        ('NONE', 'Sense comunicació'),
    ]
    communication_type = models.CharField(max_length=10, choices=COMMUNICATION_CHOICES, default='DIGITAL')
    person_contact_sms = models.ManyToManyField(PersonContact, related_name='contract_contact_sms', blank=True)
    person_contact_email = models.ForeignKey(PersonContact, on_delete=models.SET_NULL, related_name='contract_contact_email', null=True, blank=True)
    bails = models.ManyToManyField(Bail, related_name='contract_bails', blank=True)
    #contract_file = models.FileField(upload_to=contract_upload_to, blank=True, null=True)
    contract_file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    remittance_date = models.IntegerField(null=True, blank=True)
    debt_management = models.ForeignKey(ContractDebtManagement, on_delete=models.SET_NULL, null=True, blank=True)
    
    simplified_invoice = models.BooleanField(default=False)
    block_billing = models.BooleanField(default=False)
    bill_full_period = models.BooleanField(default=False, verbose_name="Facturar Període Complert")
    
    piggy_bank = models.ForeignKey(PiggyBank, on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')
    last_debt_data = models.DateField(null=True, blank=True)
    
    general_invoice = models.ForeignKey(GeneralInvoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')
    registration_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)

    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts')

    # MOVED TO GENERAL PAYMENT, UNCOMMENTED FOR NOW DUE TO MIGRATION ORDER
    mandate_id = models.CharField(max_length=255, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Contract"
        verbose_name_plural = "Contracts"
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['holder']),
        ]

    @property
    def is_fire(self):
        # Prefer queryset annotation from contract_list_page_queryset when present.
        annotated = self.__dict__.get('is_fire_annotated')
        if annotated is not None and not callable(annotated):
            return bool(annotated)

        from contract.utils.contract_list_queryset import _fire_config_tokens
        fire_usage_tokens, fire_connection_token = _fire_config_tokens()

        is_fire_contract = self.use_type and self.use_type.token in fire_usage_tokens
        if is_fire_contract:
            return True

        for sp in self.supply_points.all():
            if (
                sp.connection
                and sp.connection.use_type
                and sp.connection.use_type.token == fire_connection_token
            ):
                return True
        return False

    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Contract ID {}".format(self.id)


class ContractLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='contract_logs')
    field_name = models.TextField(null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    operation_token = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f'ContractLog {self.token} '


class ContractPriceRateHistory(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='price_rate_histories')
    price_rate = models.ForeignKey('pricing.PriceRate', on_delete=models.CASCADE, related_name='price_rate_histories')
    billing_range = models.ForeignKey('pricing.BillingRange', on_delete=models.SET_NULL, null=True, blank=True, related_name='price_rate_histories')
    is_active = models.BooleanField(default=True)

class ContractTerminationRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, related_name='contract_termination_requests', null=True, blank=True)
    claim_request = models.ForeignKey('claimrequest.ClaimRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_termination_requests')
    
    type = models.ForeignKey(ContractTerminationType, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey(ContractTerminationStatus, on_delete=models.SET_NULL, null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    termination_file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_termination_requests')
    readings = models.ManyToManyField('billing.Reading', related_name='contract_termination_requests', blank=True)
    bill_cut_reading = models.BooleanField(default=False)
    ignore_invoice = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Contract Termination Request"
        verbose_name_plural = "Contract Termination Requests"
    
    def __str__(self):
        return f'ContractSurrogation {self.token} '

class ContractRepresentative(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='representatives', null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(ContractRepresentativeType, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Contract Representative ID {}".format(self.id)

def contract_request_upload_to(instance, filename):
    return f'uploads/contract/contract-requests/{instance.id}/{filename}'

class ContractRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    language = models.CharField(max_length=2, choices=settings.LANGUAGES, default=settings.LANGUAGE)

    # contract_termination_id = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True)
    # contract_termination_lecture = models.IntegerField(null=True, blank=True)
    
    supply_point_default = models.ForeignKey(SupplyPoint, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Request SupplyPoint Default")
    supply_points = models.ManyToManyField(SupplyPoint, blank=True, related_name="supply_points_contract_request")
    
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, related_name='contract_requests', null=True, blank=True)
    contract_file_template = models.FileField(upload_to=contract_request_upload_to, null=True, blank=True)
    contract_file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(ContractRequestType, on_delete=models.SET_NULL, null=True, blank=True)

    address_billing = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Billing Address", related_name="contracts_requests_billing")
    address_contact = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Contact Address", related_name="contracts_requests_contract")
    payment = models.ForeignKey('billing.GeneralPayment', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Payment")

    # Persons
    owner = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Owner", related_name="contract_request_owner")
    tenant = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Contract Tenant", related_name="contract_request_tenant")
    holder = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True,verbose_name="Contract Holder", related_name='contract_request_holder')
    total_persons = models.IntegerField(default=3, validators=[MinValueValidator(1)])
    remittance_date = models.IntegerField(null=True, blank=True)
    
    # Comunication
    COMMUNICATION_CHOICES = [
        ('PAPER', 'Paper'),
        ('PHYSICAL', 'Física'),
        ('DIGITAL', 'Digital'),
        ('BOTH', 'Ambdues'),
        ('NONE', 'Sense comunicació'),
    ]
    communication_type = models.CharField(max_length=10, choices=COMMUNICATION_CHOICES, default='DIGITAL')
    person_contact_email = models.ForeignKey(PersonContact, on_delete=models.SET_NULL, related_name='contract_requests_contact_email', null=True, blank=True)
    person_contact_sms = models.ManyToManyField(PersonContact, related_name='contract_requests_contact_sms', blank=True)
    contacts = models.ManyToManyField(PersonContact, related_name='contract_requests_contacts', blank=True)
    
    order_types = models.ManyToManyField(OrderType, related_name='contract_requests_order_types', blank=True)
    bail_types = models.ManyToManyField(BailType, related_name='contract_requests_bail_types', blank=True)
    contract_termination_requests = models.ManyToManyField(ContractTerminationRequest, related_name='contract_requests_termination_requests', blank=True)
    
    status = models.ForeignKey(ContractRequestStatus, on_delete=models.SET_NULL, null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    use_general_price_rates = models.BooleanField(default=False)
    registration_price_rates = models.ManyToManyField('pricing.PriceRate', related_name='contract_requests_registration_price_rates', blank=True)
    price_rates = models.ManyToManyField(ContractPriceRate, related_name='contract_requests_price_rates', blank=True)
    use_type = models.ForeignKey(ContractUseType, on_delete=models.SET_NULL, null=True, blank=True)
    client_type = models.ForeignKey(ContractClientType, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(ContractCategory, on_delete=models.SET_NULL, null=True, blank=True)
    debt_management = models.ForeignKey(ContractDebtManagement, on_delete=models.SET_NULL, null=True, blank=True)
    cnaes = models.ManyToManyField(PersonCNAE, related_name='contract_requests', blank=True)

    requested_meter_caliber = models.ForeignKey('service.MeterCaliber', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Meter Caliber")

    METER_MODE_CHOICES = [
        ('real', 'Comptador real'),
        ('fictional', 'Comptador fictici'),
        ('none', 'Sense comptador'),
    ]
    meter_mode = models.CharField(max_length=10, choices=METER_MODE_CHOICES, default='real')

    registration_date = models.DateField(null=True, blank=True)
    bill_cut_reading = models.BooleanField(default=False)
    bill_full_period = models.BooleanField(default=False, verbose_name="Facturar Període Complert")
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_requests')
    
    mandate_id = models.CharField(max_length=255, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_change_of_name = models.BooleanField(default=False, verbose_name="Is Change Of Name")
    keep_same_code = models.BooleanField(default=False, verbose_name="Keep Same Code")

    class Meta:
        verbose_name = "Contract Request"
        verbose_name_plural = "Contract Requests"
    
    def __str__(self):
        return f'ContractRequest {self.token} '

class ContractClause(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name="clauses")
    contract_request = models.ForeignKey(ContractRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="clauses")
    title = models.CharField(max_length=255, null=True, blank=True)
    clause = models.TextField(null=True, blank=True)
    template = models.ForeignKey('ClauseTemplate', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "ContractClause ID {}".format(self.id)

class ContractRequestRepresentative(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    contract_request = models.ForeignKey(ContractRequest, on_delete=models.CASCADE, related_name='representatives', null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(ContractRepresentativeType, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Contract Representative ID {}".format(self.id)


class ClauseTemplate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    clause = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Clauses Template ID{}".format(self.id)

class Bonification(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    start_at = models.DateField(null=True, blank=True)
    end_at = models.DateField(null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    bonification_type = models.ForeignKey(BonificationType, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonifications')
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonifications')
    contract_request = models.ForeignKey(ContractRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='bonifications')
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, related_name='bonifications', null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Bonification"
        verbose_name_plural = "Bonifications"
    
    def __str__(self):
        return f'Bonification {self.token} '

class ContractDataChange(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='data_changes')
    new_payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_payment')
    previous_payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_previous_payment')
    new_payment = models.ForeignKey(PersonBank, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_payment')
    previous_payment = models.ForeignKey(PersonBank, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_previous_payment')
    new_person_contact_email = models.ForeignKey(PersonContact, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_contact_email')
    previous_person_contact_email = models.ForeignKey(PersonContact, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_previous_contact_email')
    new_address_contact = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_contact_address')
    previous_address_contact = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_previous_contact_address')
    new_address_billing = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_billing_address')
    previous_address_billing = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_previous_billing_address')
    new_language = models.CharField(max_length=2, choices=settings.LANGUAGES, null=True, blank=True)
    previous_language = models.CharField(max_length=2, choices=settings.LANGUAGES, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contract_data_change_user')
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f'ContractDataChange {self.token} '

class ContractTenantChange(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='tenant_changes')
    new_tenant = models.ForeignKey(Person, on_delete=models.SET_NULL, related_name='contract_tenant_change_holder', null=True, blank=True)
    previous_tenant = models.ForeignKey(Person, on_delete=models.SET_NULL, related_name='contract_tenant_change_prevoious_holder', null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f'ContractTenantChange {self.token} '
    
class ContractSurrogation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, null=True, blank=True, related_name='surrogations')
    new_holder = models.ForeignKey(Person, on_delete=models.SET_NULL, related_name='contract_surrogation_holder', null=True, blank=True)
    previous_holder = models.ForeignKey(Person, on_delete=models.SET_NULL, related_name='contract_surrogation_prevoious_holder', null=True, blank=True)
    new_payment = models.ForeignKey('billing.GeneralPayment', on_delete=models.SET_NULL, related_name='contract_surrogation_new_payment', null=True, blank=True)
    previous_payment = models.ForeignKey('billing.GeneralPayment', on_delete=models.SET_NULL, related_name='contract_surrogation_previous_payment', null=True, blank=True)
    type = models.ForeignKey(ContractSurrogationType, on_delete=models.CASCADE, null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f'ContractSurrogation {self.token} '

       
class ContractTenantChangeDocumentType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_mandatory = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name if self.name else "ContractTenantChangeDocumentType ID {}".format(self.token)    

class ContractSurrogationDocumentType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_mandatory = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name if self.name else "ContractSurrogationDocumentType ID {}".format(self.token)    

def contract_surrogation_documentation_upload_to(instance, filename):
    return f'uploads/contract-termination/documentation/{instance.id}/{filename}'

class ContractSurrogationDocument(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    checked = models.BooleanField(default=False)
    contract_surrogation = models.ForeignKey(ContractSurrogation, related_name='documents', null=True, blank=True, on_delete=models.CASCADE)
    contract_surrogation_document_type = models.ForeignKey(ContractSurrogationDocumentType, null=True, blank=True, related_name='documents', on_delete=models.CASCADE)
    file = models.FileField(upload_to=contract_surrogation_documentation_upload_to, null=True, blank=True)

    def __str__(self):
        return f"Documentation for {self.contract_surrogation.token}"

def bonification_request_documentation_upload_to(instance, filename):
    return f'uploads/bonification-requests/documentation/{instance.id}/{filename}'

def bonification_documentation_upload_to(instance, filename):
    return f'uploads/bonification/documentation/{instance.id}/{filename}'

class BonificationDocumentation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    bonification = models.ForeignKey(Bonification, on_delete=models.CASCADE, related_name='documentation_files', null=True, blank=True)
    type = models.ForeignKey(BonificationTypeDocumentationType, on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to=bonification_documentation_upload_to, null=True, blank=True)

    def __str__(self):
        return f"Documentation for {self.bonification.token}"


def contract_request_documentation_upload_to(instance, filename):
    return f'uploads/contract/documentation/{instance.contract_request.token if instance.contract_request else instance.contract.token}/{filename}'

class ContractRequestDocumentation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    contract_request = models.ForeignKey(ContractRequest, on_delete=models.SET_NULL, related_name='documentation_files', null=True, blank=True)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, related_name='documentation_files', null=True, blank=True)
    type = models.ForeignKey(ContractRequestDocumentationType, on_delete=models.SET_NULL, null=True, blank=True)
    contract_type = models.ForeignKey(ContractDocumentationType, on_delete=models.SET_NULL, null=True, blank=True)
    #file = models.FileField(upload_to=contract_request_documentation_upload_to, null=True, blank=True)
    file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    text = models.CharField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"Documentation for {self.contract_request.token if self.contract_request else self.contract.token}"
#
# Taules de suport (observacions)
#
class ContractObservation(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(ContractStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_important = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "SupplyPointObservation {}".format(self.id)

class ContractRequestObservation(models.Model):
    contract_request = models.ForeignKey(ContractRequest, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(ContractRequestStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "ContractRequestObservation {}".format(self.id)
        
        
class ContractTerminationRequestObservation(models.Model):
    contract_termination = models.ForeignKey(ContractTerminationRequest, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(ContractRequestStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "ContractRequestObservation {}".format(self.id)

class ACADocumentStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ACADocumentStatus ID {}".format(self.token)

def aca_documentation_upload_to(instance, filename):
    return f'uploads/contracts/aca/documentation/{instance.id}/{filename}'

class ACADocument(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    file = models.FileField(upload_to=aca_documentation_upload_to, null=True, blank=True)
    
    status = models.ForeignKey(ACADocumentStatus, on_delete=models.SET_NULL, null=True, blank=True)
    
    name = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    supplier = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=255, null=True, blank=True)
    number = models.CharField(max_length=255, null=True, blank=True)
    closing = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "ACA Document"
        verbose_name_plural = "ACA Documents"
        
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Contract ID {}".format(self.id)
        
class ACADocumentChange(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    aca_document = models.ForeignKey(ACADocument, on_delete=models.CASCADE, null=True, blank=True, related_name="document_changes")

    person_name = models.CharField(max_length=255, null=True, blank=True)
    person_NIF = models.CharField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=255, null=True, blank=True)
    city_code = models.CharField(max_length=255, null=True, blank=True)
    contract_code = models.CharField(max_length=255, null=True, blank=True)

    accepted = models.BooleanField(default=False)

    # Només per als fitxers d'intercanvi TXT de 350 posicions (documents 04 i 05 de l'ACA,
    # veure contract/utils/aca_exchange_file_parser.py); els HTML de l'ACA no les porten.
    request_date = models.DateField(null=True, blank=True)
    num_persons = models.CharField(max_length=2, null=True, blank=True)
    # Només CS (tarifa social): col·lectiu (llista 5.3 del document 05 de l'ACA) i, si és
    # 92, el nom del fitxer de l'informe col·lectiu.
    social_collective = models.CharField(max_length=2, null=True, blank=True)
    collective_report = models.CharField(max_length=22, null=True, blank=True)
    aca_result = models.CharField(max_length=2, null=True, blank=True)
    closing = models.BooleanField(default=False)

    # Bonificació creada (o tancada) en processar el document: evita aplicar-la dues
    # vegades si el document es torna a desar amb l'estat "processat".
    bonification = models.ForeignKey(Bonification, on_delete=models.SET_NULL, null=True, blank=True, related_name='aca_document_changes')
    applied_at = models.DateTimeField(null=True, blank=True)


class ACABonificationRequest(models.Model):
    """Sol·licitud d'ampliació de trams pendent de notificar a l'ACA.

    Es crea automàticament quan es dona d'alta a un contracte una Bonification
    del tipus configurat a ConfigProject 'aca_at_token' (veure contract/signals.py).
    """
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    bonification = models.OneToOneField(Bonification, on_delete=models.CASCADE, related_name='aca_request')

    num_persons_to_apply = models.PositiveSmallIntegerField(null=True, blank=True)
    authorizes_census_review = models.BooleanField(null=True, blank=True)

    # Revisió interna de l'entitat subministradora abans d'enviar la sol·licitud
    # (llistes de valors 5.3/5.4 i 5.5 del document de l'ACA).
    ACA_RESULT_CHOICES = [
        ('01', "Acompleix requisits d'ampliació"),
        ('02', 'No és titular del contracte'),
        ('03', 'No disposa de comptador individual'),
        ('04', 'No són usos domèstics'),
        ('05', 'El titular del contracte no és persona física'),
        ('06', "Nombre d'habitants inferior a 4"),
        ('07', 'Ja disposa de la condició d\'ampliació'),
        ('08', 'La companyia no subministra en l\'adreça de la sol·licitud'),
        ('20', 'Tancament. No titular del contracte'),
        ('21', 'Tancament. 3 o menys persones'),
        ('22', 'Tancament. Baixa padró o canvi adreça'),
    ]
    aca_result = models.CharField(max_length=2, choices=ACA_RESULT_CHOICES, null=True, blank=True)

    CENSAT_ADRECA_CHOICES = [
        ('1', "Censat en l'adreça"),
        ('2', "No censat en l'adreça"),
        ('3', 'No validat'),
    ]
    censat_adreca = models.CharField(max_length=1, choices=CENSAT_ADRECA_CHOICES, null=True, blank=True)
    num_persons_censats = models.PositiveSmallIntegerField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    aca_document = models.ForeignKey(ACADocument, on_delete=models.SET_NULL, null=True, blank=True, related_name='aca_bonification_requests')

    def __str__(self):
        return f"ACABonificationRequest {self.bonification_id}"


class ContractDebtView(models.Model):
    """Lectura de la vista SQL vw_contract_debt (statistics/migrations/0033_create_vw_contract_debt.py).
    Única definició de deute per contracte: la fan servir el detall, el llistat, el
    filtre has_debt, l'ordenació per deute i les exportacions, via
    contract.utils.contract_list_queryset.contract_debt_amounts_by_contract_id.
    Els pagaments negatius no hi resten
    (statistics/migrations/0039_vw_contract_debt_no_negative.py): el deute d'un
    contracte no pot ser mai negatiu."""
    contract_token = models.CharField(max_length=255, primary_key=True)
    debt_amount = models.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'vw_contract_debt'