# coredata/models.py
from django.db import models
from django.contrib.auth.models import User
from documentmanager.models import Document
from coredata.utils.validators_utils import is_valid_dni

class ConfigProject(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    value = models.TextField(null=True, blank=True)
    file = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.token if self.token else "ConfigProject ID {}".format(self.id)


class MainPermission(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255)
    view_key = models.CharField(max_length=255)
    change_key = models.CharField(max_length=255)
    affected_models = models.TextField(blank=True, null=True)
    all_recommended = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class Country(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    name = models.CharField(max_length=100)
    in_europe = models.BooleanField(default=False)
    is_sepa = models.BooleanField(default=False)
    has_iban = models.BooleanField(default=False)
    iso_code = models.CharField(max_length=3, unique=False)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    

class StreetType(models.Model):
    """Catàleg dels 71 tipus de via oficials de l'ACA.

    La llista viu a `coredata/aca_street_types.py`, el fixture
    `initial_data/ca/coredata.StreetType.json` la carrega i `manage.py sync_street_types` la
    torna a posar al dia. La taula NO està bloquejada: el que impedeix que torni a créixer
    sola és que ningú hi fa `get_or_create`. Per resoldre un tipus de via, passeu sempre per
    `coredata/street_types.py` — un tipus que no és a la llista no es crea.
    """

    abbreviation = models.CharField(max_length=120, blank=True, null=True)
    aca_abbreviation = models.CharField(max_length=120, blank=True, null=True)
    name = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.name} ({self.aca_abbreviation})"

class IdentificationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name

class Province(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True)
    is_default = models.BooleanField(default=False)
    def __str__(self):
        return self.name
    
class City(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    province = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class PostalCode(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    code = models.CharField(max_length=120, unique=True)
    province = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True)
    cities = models.ManyToManyField(City, related_name='postal_codes')

    def __str__(self):
        return self.code



class Street(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    type = models.ForeignKey(StreetType, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    name_2 = models.CharField(max_length=100, null=True, blank=True)  # Per a noms addicionals o segments
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        secondary = f" / {self.name_2}" if self.name_2 else ""
        if self.type and self.type.abbreviation:
            return f"{self.type.abbreviation + '. ' if self.type else ''}{self.name}{secondary}"
        else:
            return f"{self.name}{secondary}"

    
class StreetNumberType(models.Model):
    TYPE_CHOICES = [
        ('N', 'Number'),
        ('SN', 'S/N'),
        ('R', 'Range'),
        ('S', 'Suffix'),
    ]
    type = models.CharField(max_length=2, choices=TYPE_CHOICES, unique=True)
    description = models.CharField(max_length=50)

    def __str__(self):
        return self.description

class StreetNumber(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    street = models.ForeignKey(Street, on_delete=models.CASCADE)
    number_type = models.ForeignKey(StreetNumberType, on_delete=models.SET_NULL, null=True)
    number = models.IntegerField(null=True, blank=True)
    number_end = models.IntegerField(null=True, blank=True)
    number_suffix = models.CharField(max_length=120, null=True, blank=True)
    number_end_suffix = models.CharField(max_length=120, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True) 
    
    def __str__(self):
        number_display = ""
        if not self.number_type:
            number_display = str(self.number) if self.number is not None else ""
        else:
            if self.number_type.type == 'N':
                number_display = str(self.number) if self.number is not None else ''
            elif self.number_type.type == 'SN':
                number_display = "S/N"
            elif self.number_type.type == 'R':
                number_display = f"{self.number if self.number is not None else ''}{self.number_suffix if self.number_suffix else ''}{f'-{self.number_end}' if self.number_end is not None else ''}{self.number_end_suffix if self.number_end_suffix else ''}"
            elif self.number_type.type == 'S':
                if self.number is not None: 
                    number_display = f"{self.number}{f'-{self.number_suffix}' if self.number_suffix else ''}"
                else:
                    number_display = f"{self.number_suffix if self.number_suffix else ''}"
            else:
                # Fallback per a tipus desconeguts
                number_display = str(self.number) if self.number is not None else ""

        return f"{number_display}".strip()


class Address(models.Model):    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    postal_code = models.CharField(max_length=120, null=True, blank=True)
    street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True)
    street_number = models.ForeignKey(StreetNumber, on_delete=models.SET_NULL, null=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True)
    province = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True)

    city_name = models.CharField(max_length=255, null=True, blank=True)
    province_name = models.CharField(max_length=255, null=True, blank=True)

    floor = models.CharField(max_length=120, null=True, blank=True)
    door = models.CharField(max_length=120, null=True, blank=True)
    stair = models.CharField(max_length=120, null=True, blank=True)
    building = models.CharField(max_length=50, null=True, blank=True)
    address_extra = models.TextField(null=True, blank=True)

    is_manual = models.BooleanField(default=False) # Indica si l'adreça ha estat introduïda manualment (lliure)

    token = models.CharField(max_length=255, null=True, blank=True)
    address_search = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        street_display = str(self.street) if self.street else ""
        number_display = str(self.street_number) if self.street_number else ""
        if number_display == "None":
            number_display = ""
        
        floor_door = []
        if self.floor:
            floor_door.append(str(self.floor))
        if self.door:
            floor_door.append(str(self.door))
        
        floor_door_display = '-'.join(floor_door)
        
        # País i localitat
        city_display = str(self.city) if self.city else (self.city_name or "")
        
        parts = []
        if street_display:
            parts.append(street_display)
        if number_display:
            # Afegim coma després del carrer si hi ha número
            if parts:
                parts[-1] = parts[-1] + ","
            parts.append(number_display)
        
        if self.stair:
            parts.append(f"Esc. {self.stair}")
        if self.building:
            parts.append(self.building)
        if floor_door_display:
            parts.append(floor_door_display)
            
        address_line = " ".join(parts).replace(", ", ", ")
        
        if (self.country and self.country.iso_code == 'ES'):
            return f"{address_line}, {city_display}".strip(", ")
        else:
            postal_code = self.postal_code or ""
            country_display = self.country.name if self.country else ""
            
            non_empty = [address_line, postal_code, city_display, country_display]
            return " - ".join([p for p in non_empty if p]).strip()

    def is_shared(self):
        count = 0
        for relation in self._meta.related_objects:
            accessor = relation.get_accessor_name()
            if accessor:
                try:
                    count += getattr(self, accessor).count()
                except Exception:
                    pass
            if count > 1:
                return True
        return False

    def save(self, *args, **kwargs):
        try:
            self.address_search = str(self).strip()
        except Exception:
            pass
        super().save(*args, **kwargs)


class Bank(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    bic = models.CharField(max_length=255, null=True, blank=True)
    #Bool from char in CSV
    active = models.CharField(max_length=1, null=True, blank=True)
    taken_by = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.name if self.name else "Bank ID {}".format(self.token)
    

class CNAE(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    
    def __str__(self):
        return self.description

class PersonDeliquency(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    is_debtor = models.BooleanField(default=False)  
    debt_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    last_debt_data = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.person.name} {self.person.surname} - debt of {self.debt_amount}"

class PersonPiggyBank(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f'PiggyBank {self.token}'
    
class PersonPiggyBankMovement(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    movement_date = models.DateField(null=True, blank=True)
    
    person_piggy_bank = models.ForeignKey(PersonPiggyBank, on_delete=models.CASCADE, related_name='person_movements')
    payment = models.ForeignKey('billing.Payment', null=True, blank=True, on_delete=models.CASCADE, related_name='person_movements')
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='person_movements') # USER WHEN REMOVING OR ADDING MANUAL MOVEMENTS
    
    is_positive = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

class Person(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    surname = models.CharField(max_length=255, null=True, blank=True)
    is_juridic = models.BooleanField(default=False)
    
    identification_type = models.ForeignKey(IdentificationType, on_delete=models.SET_NULL, null=True, blank=True, related_name='person')
    dni_validated = models.BooleanField(default=False)
    vulnerability_level = models.IntegerField(default=0) # 0: No vulnerable, 1: En Risc, 2: Vulnerable
    deliquency = models.ForeignKey(PersonDeliquency, on_delete=models.SET_NULL, null=True, blank=True, related_name='person')
    #commitment_deposit = models.ForeignKey('billing.CommitmentDeposit', on_delete=models.SET_NULL, null=True, blank=True, related_name='person')
    
    piggy_bank = models.ForeignKey(PersonPiggyBank, on_delete=models.SET_NULL, null=True, blank=True, related_name='person')
    # e_record = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        verbose_name = "Person"
        verbose_name_plural = "Persons"

    def __str__(self):
        return f"{self.name} {self.surname if self.surname else ''}"

    def save(self, *args, **kwargs):
        # Nota: accedir a self.identification_type fa una query extra si la FK
        # no està prefetched. Assumible per save() individuals; si en algun
        # moment fem bulk-save de Person, considerar cachejar el token abans.
        if self.identification_type_id and self.identification_type.token == 'dni':
            self.dni_validated = is_valid_dni(self.token)
        else:
            self.dni_validated = False

        super().save(*args, **kwargs)

class PersonLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='person_logs')
    field_name = models.TextField(null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    operation_token = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'PersonLog {self.id}'

class PersonRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, null=True, blank=True, related_name='records')
    year = models.IntegerField(null=True, blank=True)
    e_record = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.person.name} {self.person.surname if self.person.surname else ''} - {self.record}"


class PersonObservation(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, null=True, blank=True, related_name='observations')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    is_important = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "PersonObservation {}".format(self.id)
    

class PersonAddress(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='addresses')
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    attention_to = models.CharField(max_length=255, null=True, blank=True)
    is_billing = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    token = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        if self.person:
            return f"{self.person.token} - {'Billing' if self.is_billing else 'Contact'} address" 
        return f"Address {self.id}"


class PersonContact(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name='contacts')
    phone = models.CharField(max_length=20, null=True, blank=True)
    role = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.person.name if self.person else None} {self.role} ({'Default' if self.is_default else 'Secondary'})"
    
    def save(self, *args, **kwargs):
        if self.person and not PersonContact.objects.filter(person=self.person).exists():
            self.is_default = True
            
        email_removed = False
        if self.pk:
            try:
                old_instance = PersonContact.objects.get(pk=self.pk)
                had_email = bool(old_instance.email and old_instance.email.strip())
                has_email_now = bool(self.email and self.email.strip())
                if had_email:
                    if not has_email_now or (old_instance.is_active and not self.is_active) or (old_instance.person_id and not self.person_id):
                        email_removed = True
            except PersonContact.DoesNotExist:
                pass
                
        super().save(*args, **kwargs)
        
        if email_removed:
            from contract.models import Contract
            contracts = Contract.objects.filter(person_contact_email=self)
            for contract in contracts:
                contract.person_contact_email = None
                if contract.communication_type != 'NONE':
                    contract.communication_type = 'PAPER'
                contract.save()

    def delete(self, *args, **kwargs):
        if self.email and self.email.strip():
            from contract.models import Contract
            contracts = Contract.objects.filter(person_contact_email=self)
            for contract in contracts:
                contract.person_contact_email = None
                if contract.communication_type != 'NONE':
                    contract.communication_type = 'PAPER'
                contract.save()
        super().delete(*args, **kwargs)

def sepa_documentation_upload_to(instance, filename):
    return f'uploads/person-bank-sepa/documentation/{instance.id}/{filename}'
def sepa_template_documentation_upload_to(instance, filename):
    return f'uploads/person-bank-sepa/documentation/template/{instance.id}/{filename}'

class CallRegister(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    person_contact = models.ForeignKey(PersonContact, on_delete=models.CASCADE, null=True, blank=True, related_name='call_registers')
    contract = models.ForeignKey('contract.Contract', on_delete=models.CASCADE, null=True, blank=True, related_name='call_registers')
    time_call = models.DateTimeField(null=True, blank=True)
    answered = models.BooleanField(default=False)
    comment = models.TextField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='call_registers')
    
    def __str__(self):
        return f"{self.person_contact.person.name if self.person_contact.person else 'Person'} - {self.contract.token if self.contract else 'No Contract'} - {self.time_call if self.time_call else 'Time call'}"

class PersonBank(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.CASCADE, null=True, blank=True, related_name='banks')
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, null=True, blank=True, related_name='person_banks')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name='banks')
    name = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=255, null=True, blank=True)
    dni = models.CharField(max_length=255, null=True, blank=True)
    account_number = models.CharField(max_length=255, null=True, blank=True)
    swift = models.CharField(max_length=255, null=True, blank=True)
    iban = models.CharField(max_length=255, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return "Payment ID {}".format(self.token)
  
    
class PersonCNAE(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="cnaes")
    cnae = models.ForeignKey(CNAE, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.person.name if self.person else 'Person'} - {self.cnae.description if self.cnae else 'CNAE'}"
    
class ReturnReason(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.code} - {self.label}"


class ExecutedScript(models.Model):
    """Tracks one-off ops scripts (coredata/management/commands/run_pending_scripts.py)
    already run on this environment, mirroring how django_migrations tracks migrations."""
    app_label = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("app_label", "name")
        ordering = ["app_label", "name"]

    def __str__(self):
        return f"{self.app_label}.{self.name}"