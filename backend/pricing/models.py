from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from contract.models import PaymentType, VariableType
from coredata.models import Bank
from service.models import Exploitation, Company

class AdjustmentOperation(models.Model):
    TYPE_CHOICES = [
        ('min', 'Minim'),
        ('max', 'Màxim'),
        ('ptg', 'Percentatge'),
        ('ext', 'Ampliació de Tram'),
        ('var', 'Variable'),
    ]
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(choices=TYPE_CHOICES, default='ptg')
    name = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.name

class ProductOrigin(models.Model):
    TYPE_CHOICES=[
        ('aigua', 'Aigua'),
        ('contracte', 'Contracte'),
        ('altres', 'Altres'),
        ('escomesa', 'Escomesa'),
        ('subministrament', 'Subministrament'),
    ]
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(choices=TYPE_CHOICES, default='aigua')
    name = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.name

class VariableCalculation(models.Model):
    TYPE_CHOICES = [
        ('price', 'Preu'),
        ('consum', 'Consum'),
        ('prev_consum', 'Consum Anterior'),
        ('dies_consum', 'Dies Consum'),
        ('diferencia_fuita', 'Diferencia de Fuita'),
        ('diferencia_fuita_consum', 'Diferencia de Fuita i Consum'),
        ('units', 'Unitats'),
    ]
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(choices=TYPE_CHOICES, default='consum')
    name = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.name

class BillingPeriod(models.Model):
    TYPE_CHOICES = [
        ('anual', 'Anual'),
        ('semestral', 'Semestral'),
        ('bimestral', 'Bimestral'),
        ('trimestral', 'Trimestral'),
        ('quadrimestral', 'Quadrimestral'),
        ('mensual', 'Mensual'),
        ('diaria', 'Diaria')
    ]
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(choices=TYPE_CHOICES, default='mensual')
    name = models.CharField(max_length=255, null=True, blank=True)
    days = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} ({self.days} days)"


class ArticleCode(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=100)
    position = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.name} ({self.token})"

class Tax(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=100)
    percent = models.FloatField(null=True, blank=True)
    start = models.DateField(null=True, blank=True)
    end = models.DateField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.name} ({self.percent} %)"

class Quantity(models.Model):
    TYPE_CHOICES = [
        ('consumreal', 'Consum Real'),
        ('adjestimacio', 'Adjustament per estimació'),
        ('adjre', 'Adjustament'),
        ('altres', 'Altres adjustaments'),
    ]
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(choices=TYPE_CHOICES, default='consumreal')
    name = models.CharField(max_length=255, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name
    


class Product(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    origin = models.ForeignKey(ProductOrigin, on_delete=models.SET_NULL, related_name='products', null=True, blank=True)
    
    product_related = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, related_name='products', null=True, blank=True)
    exploitation = models.ForeignKey(Exploitation, on_delete=models.SET_NULL, related_name='price_rates', null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    billing_active = models.BooleanField(default=True)
    billing_inactive = models.BooleanField(default=True)
    
    order_priority = models.IntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
    
    def __str__(self):
        if self.name:
            return self.name
        else:
            return "Product ID {}".format(self.id)


class ProductI18n(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=2, choices=settings.LANGUAGES)
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('product', 'language')

    def __str__(self):
        return f"Product {self.product_id} [{self.language}] {self.name}"


class PriceRate(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    product = models.ForeignKey(Product, on_delete=models.SET_NULL, related_name='price_rates', null=True, blank=True)
    billing_range_active = models.ForeignKey("BillingRange", on_delete=models.SET_NULL, related_name='price_rates', null=True, blank=True)

    is_bail = models.BooleanField(default=False)
    # Marca la tarifa de despeses de devolucio. Nomes n'hi pot haver una: en
    # marcar-la, `sync_return_fee_config()` desmarca la que hi hagues i deixa
    # els ConfigProject de `RETURN_FEE_CONFIG_TOKENS` apuntant al seu token.
    is_return_fee = models.BooleanField(default=False)
    #is_process_fee = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Price Rate"
        verbose_name_plural = "Price Rates"
        
    def __str__(self):
        if self.name:
            return self.name
        elif self.token:
            return self.token
        else:
            return "PriceRate ID {}".format(self.id)


class PriceRateI18n(models.Model):
    price_rate = models.ForeignKey(PriceRate, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=2, choices=settings.LANGUAGES)
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('price_rate', 'language')

    def __str__(self):
        return f"PriceRate {self.price_rate_id} [{self.language}] {self.name}"


class Publication(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Publication Name")
    boe_number = models.CharField(max_length=50, null=True, blank=True, verbose_name="BOE Number")
    boe_date = models.DateField(null=True, blank=True, verbose_name="BOE Date")
    reference = models.CharField(max_length=100, null=True, blank=True, unique=True, verbose_name = "Reference BOE")
    content = models.TextField(null=True, blank=True, verbose_name="Content BOE")
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Amount")
    
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.name and self.boe_number:
            return self.name + " - BOE: " + self.boe_number
        else:
            return "Publication ID {}".format(self.id)


class BillingRange(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='billing_ranges',null=True, blank=True)
    price_rate = models.ForeignKey(PriceRate, on_delete=models.CASCADE, related_name='billing_ranges',null=True, blank=True)
    
    name = models.CharField(max_length=255, null=True, blank=True)
    start = models.DateField(null=True, blank=True)
    end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.name:
            return self.name
        else:
            return "BillingRange ID {}".format(self.id)



class PriceInterval(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    TYPE_CHOICES=[
        ('m3', 'm3'),
        ('dm_met', 'diametre_met'),
        ('dm_con', 'diametre_conn'),
    ]
    units = models.CharField(choices=TYPE_CHOICES, default='m3')
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.token if self.token else "PriceInterval ID {}".format(self.id)
   

class PriceIntervalStretch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name_stretch = models.CharField(max_length=255, null=True, blank=True)
    
    price_interval = models.ForeignKey(PriceInterval, on_delete=models.SET_NULL, related_name='price_interval_stretches', null=True, blank=True)
    
    price = models.FloatField(null=True, blank=True)
    proportional_price = models.FloatField(null=True, blank=True)
    
    stretch = models.IntegerField(null=True, blank=True)
    end_stretch = models.IntegerField(null=True, blank=True)
    
    article = models.ForeignKey(ArticleCode, on_delete=models.SET_NULL, related_name='price_interval_stretches',null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return "PriceIntervalStretch ID {}".format(self.id)


class PriceIntervalStretchI18n(models.Model):
    price_interval_stretch = models.ForeignKey(PriceIntervalStretch, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=2, choices=settings.LANGUAGES)
    name_stretch = models.CharField(max_length=255)

    class Meta:
        unique_together = ('price_interval_stretch', 'language')

    def __str__(self):
        return f"PriceIntervalStretch {self.price_interval_stretch_id} [{self.language}] {self.name_stretch}"


class PriceVariableInterval(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    TYPE_CHOICES=[
        ('m3', 'm3'),
        ('dm_met', 'diametre_met'),
        ('dm_con', 'diametre_conn'),
    ]
    units = models.CharField(choices=TYPE_CHOICES, default='m3')
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return "PriceInterval ID {}".format(self.id)
   

class PriceVariableIntervalStretch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name_stretch = models.CharField(max_length=255, null=True, blank=True)
    
    price = models.FloatField(null=True, blank=True)
    proportional_price = models.FloatField(null=True, blank=True)
    
    stretch = models.IntegerField(null=True, blank=True)
    end_stretch = models.IntegerField(null=True, blank=True)
    price_variable_interval = models.ForeignKey(PriceVariableInterval, on_delete=models.SET_NULL, related_name='price_variable_interval_stretches', null=True, blank=True)
    
    article = models.ForeignKey(ArticleCode, on_delete=models.SET_NULL, related_name='price_variable_stretches',null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return "PriceIntervalStretch ID {}".format(self.id)




class LineItemType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    billing_range = models.ForeignKey(BillingRange, on_delete=models.CASCADE, related_name='line_item_types',null=True, blank=True)
    
    formula = models.TextField(null=True, blank=True)
    price = models.FloatField(null=True, blank=True)
    proportional_price = models.FloatField(null=True, blank=True)
    quantity = models.ForeignKey(VariableCalculation, on_delete=models.CASCADE, related_name='line_item_types',null=True, blank=True)
    price_interval = models.ForeignKey(PriceInterval, on_delete=models.CASCADE, related_name='line_item_types',null=True, blank=True)
    price_variable = models.ForeignKey(PriceVariableInterval, on_delete=models.CASCADE, related_name='line_item_types',null=True, blank=True)
    operation = models.CharField(max_length=255, null=True, blank=True)
    
    CHOICES = [
        ('DAYS', 'Correcció per dies'),
        ('MONTHS', 'Correcció per mesos'),
        ('NOADJ', 'Sense correcció'),
    ]
    active_choice = models.CharField(max_length=255, null=True, blank=True, choices=CHOICES, default='NOADJ')
    inactive_choice = models.CharField(max_length=255, null=True, blank=True, choices=CHOICES, default='NOADJ')
    is_positive = models.BooleanField(default=True)
    
    is_prorated = models.BooleanField(default=False)
    
    billing_period = models.ForeignKey(BillingPeriod, on_delete=models.CASCADE, related_name='line_item_type',null=True, blank=True)
    tax = models.ForeignKey(Tax, on_delete=models.CASCADE, related_name='line_item_type',null=True, blank=True)
    
    article = models.ForeignKey(ArticleCode, on_delete=models.SET_NULL, related_name='line_item_types',null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    always_show = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.name + ' - ' + self.token


class LineItemTypeI18n(models.Model):
    line_item_type = models.ForeignKey(LineItemType, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=2, choices=settings.LANGUAGES)
    name = models.CharField(max_length=255)

    class Meta:
        unique_together = ('line_item_type', 'language')

    def __str__(self):
        return f"LineItemType {self.line_item_type_id} [{self.language}] {self.name}"


class Adjustment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    start_at = models.DateField(null=True, blank=True)
    end_at = models.DateField(null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    
    operation = models.ForeignKey(AdjustmentOperation, on_delete=models.CASCADE, related_name='adjustments',null=True, blank=True)
    variable_calculation = models.ForeignKey(VariableCalculation, on_delete=models.SET_NULL, related_name='adjustments',null=True, blank=True)
    variable_type = models.ForeignKey(VariableType, on_delete=models.SET_NULL, related_name='adjustments',null=True, blank=True)
    quantity = models.FloatField(null=True, blank=True)
    formula = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    
    line_item_type = models.ForeignKey(LineItemType, on_delete=models.SET_NULL, related_name='adjustments',null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.token


class AdjustmentIntervalStretch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    
    adjustment = models.ForeignKey(Adjustment, on_delete=models.CASCADE, related_name='adjustment_interval_stretches',null=True, blank=True)
    price_variable_stretch = models.ForeignKey(PriceVariableIntervalStretch, on_delete=models.CASCADE, related_name='adjustments',null=True, blank=True)
    price_interval_stretch = models.ForeignKey(PriceIntervalStretch, on_delete=models.CASCADE, related_name='adjustments',null=True, blank=True)
    coefficient = models.FloatField(null=True, blank=True)
    formula = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return "AdjustmentInterval ID {}".format(self.id)

class AdjustmentCondition(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    adjustment = models.ForeignKey(Adjustment, on_delete=models.CASCADE, related_name='conditions', null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.JSONField(null=True, blank=True)
    OPERATION_CHOICES=[
        ('eq', 'Equal'),
        ('ne', 'Not Equal'),
        ('gt', 'Greater Than'),
        ('lt', 'Less Than'),
        ('ge', 'Greater or Equal'),
        ('le', 'Less or Equal'),
        ('in', 'In'),
        ('ni', 'Not In'),
        ('is_true', 'Is True'),
        ('is_false', 'Is False'),
        ('is_null', 'Is Null'),
        ('is_not_null', 'Is Not Null')
    ]
    operation = models.CharField(choices=OPERATION_CHOICES, default='eq')
    formula = models.TextField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"Condition {self.name}..."


class AccountingType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    add_taxes = models.BooleanField(default=False)
    add_subtotals = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"AccountingType {self.name}"

class AccountingCostCenter(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"AccountingType {self.name}"
    
class AccountingConcept(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    
    CATEGORY_CHOICES = {
        ('invoice', 'Invoice'),
        ('lineitem', 'Line Item'),
        ('payment', 'Payment'),
    }
    category = models.CharField(choices=CATEGORY_CHOICES, default='invoice')
    type = models.ForeignKey(AccountingType, on_delete=models.CASCADE, related_name='accounting_concepts', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"AccountingConcept {self.name}"

class AccountingPricing(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_accounting_pricings')
    last_updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='last_updated_accounting_pricings')
    
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
    accounting_concept = models.ForeignKey(AccountingConcept, on_delete=models.SET_NULL, related_name='accounting_pricings', null=True, blank=True)
    accounting_cost_center = models.ForeignKey(AccountingCostCenter, on_delete=models.SET_NULL, related_name='accounting_pricings', null=True, blank=True)
    #invoices category
    invoice_category = models.CharField(max_length=255, null=True, blank=True) # normal - irrecoverable - endownment
    undeclare_previous = models.BooleanField(default=False) # if TRUE, undeclare previous declarations (example, declared normal invoice set as endowment will be firt subtracted from normal invoices accounting and then declared on endowment accounting)
    origins = models.ManyToManyField(ProductOrigin, related_name='accounting_pricings') # declare only if separated by these, otherwise all together
    # lineitem category
    products = models.ManyToManyField(Product, related_name='accounting_pricings')
    price_rates = models.ManyToManyField(PriceRate, related_name='accounting_pricings')
    line_item_types = models.ManyToManyField(LineItemType, related_name='accounting_pricings')
    price_intervals = models.ManyToManyField(PriceInterval, related_name='accounting_pricings')
    price_variables = models.ManyToManyField(PriceVariableInterval, related_name='accounting_pricings')
    # payment category
    payment_types = models.ManyToManyField(PaymentType, related_name='accounting_pricings')
    banks = models.ManyToManyField(Bank, related_name='accounting_pricings') # handled if DIRECT_DEBIT and BANK_TRANSFER (when returns)
    national_iban = models.BooleanField(default=False) # handled if DIRECT_DEBIT
    foreign_iban = models.BooleanField(default=False) # handled if DIRECT_DEBIT
    outgoing_payments = models.BooleanField(default=False) # handled if BANK_TRANSFER
    incoming_payments = models.BooleanField(default=False) # handled if BANK_TRANSFER
    
    grouped_lines = models.BooleanField(default=True) # if FALSE, each value will be a separate line
    
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, related_name='accounting_pricings', null=True, blank=True)
    exploitation = models.ForeignKey(Exploitation, on_delete=models.SET_NULL, related_name='accounting_pricings', null=True, blank=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"AccountingPricing {self.name}"