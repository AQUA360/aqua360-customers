# service/models.py

from django.conf import settings
from django.db import models
from coredata.models import Address, Bank, Country, PersonAddress, Street, StreetNumber, PostalCode, Person, City
from django.contrib.auth.models import User
from documentmanager.models import Document

#
# Taules mestres
#

class CompanyType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    
    def __str__(self):
        return self.name if self.name else "CompanyType ID {}".format(self.token)


class ConnectionStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ConnectionStatus ID {}".format(self.token)

class ConnectionType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ConnectionType ID {}".format(self.token)


class ConnectionUseType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ConnectionUseType ID {}".format(self.token)

class ConnectionInstallationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ConnectionInstallationType ID {}".format(self.token)


class ConnectionValveType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ConnectionValveType ID {}".format(self.token)


class ConnectionMaterial(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ConnectionMaterial ID {}".format(self.token)


class ConnectionDiameter(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ConnectionDiameter ID {}".format(self.token)

class ConnectionRequestStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ConnectionRequestStatus ID {}".format(self.token)

class ClusterStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ClusterStatus ID {}".format(self.token)

class ClusterNozzleStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ClusterNozzleStatus ID {}".format(self.token)

class ClusterNozzleType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "ClusterNozzleType ID {}".format(self.token)


class MeterStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "MeterStatus ID {}".format(self.token)

class MeterCaliber(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "MeterCaliber ID {}".format(self.token)

class SupplyPointType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "SupplyPointType ID {}".format(self.token)


class SupplyPointStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "SupplyPointStatus ID {}".format(self.token)

class SupplyPointSource(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "SupplyPointSource ID {}".format(self.token)

class SupplyPointSupplyType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "SupplyPointSupplyType ID {}".format(self.token)

class SupplyPointPlacement(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name if self.name else "SupplyPointPlacement ID {}".format(self.token)


#
# Taules de negoci
#

class CompanyConfig(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    token = models.CharField(max_length=255, null=True, blank=True) #settings name for email pwd
    name = models.CharField(max_length=255, null=True, blank=True) #conf name
    
    SERVICE_CHOICES = [
        ('smtp', 'SMTP'),
        ('gmail', 'Gmail'),
    ]
    mail_send_service = models.CharField(max_length=255, null=True, blank=True, choices=SERVICE_CHOICES) #UNUSED
    mail_send_smtp_server = models.CharField(max_length=255, null=True, blank=True) #EMAIL_HOST
    mail_send_smtp_port = models.IntegerField(null=True, blank=True) #EMAIL_PORT
    mail_send_contact_footer = models.EmailField(null=True, blank=True)

    use_TLS = models.BooleanField(null=True, blank=True)
    use_SSL = models.BooleanField(null=True, blank=True)
    
    def __str__(self):
        return "CompanyConfig ID {}".format(self.id)

class CompanyConfigEmail(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    company_config = models.ForeignKey(CompanyConfig, on_delete=models.CASCADE, null=True, blank=True, related_name='company_config_emails')
    
    mail_send_user = models.CharField(max_length=255, null=True, blank=True)
    mail_send_mail = models.EmailField(null=True, blank=True) #EMAIL_HOST_USER
    use_type = models.ForeignKey('communication.CommunicationUseType', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Connection Use Type")
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return "CompanyConfigEmail ID {}".format(self.id)

class Company(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    def logo_file_upload_to(instance, filename):
        # Genera el camí de càrrega utilitzant l'ID de la connexió
        return f'uploads/logo/{instance.id}/{filename}'
    name = models.CharField(max_length=255, null=True, blank=True)
    alias = models.CharField(max_length=255, null=True, blank=True)
    vat = models.CharField(max_length=255, null=True, blank=True)
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True)
    logo = models.ImageField(upload_to=logo_file_upload_to, null=True, blank=True)
    phone = models.CharField(max_length=255, null=True, blank=True)
    phone2 = models.CharField(max_length=255, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    email =  models.EmailField(null=True, blank=True)
    contact_name = models.CharField(max_length=255, null=True, blank=True)
    contact_phone = models.CharField(max_length=255, null=True, blank=True)
    contact_email = models.CharField(max_length=255, null=True, blank=True)
    barcode_ident = models.CharField(max_length=255, null=True, blank=True)
    supply_code = models.CharField(max_length=255, null=True, blank=True)
    type = models.ForeignKey(CompanyType, on_delete=models.SET_NULL, null=True, blank=True, related_name='companies')
    config = models.ForeignKey(CompanyConfig, on_delete=models.SET_NULL, null=True, blank=True, related_name='company_configs')
    
    invoice_main_color = models.CharField(max_length=10, null=True, blank=True)
    invoice_secondary_color = models.CharField(max_length=10, null=True, blank=True)
    
    invoice_footer_text = models.TextField(null=True, blank=True)
    data_protection_law_text = models.TextField(null=True, blank=True)
    
    is_provider = models.BooleanField(default=False)

    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name


class CompanyInvoiceFooterTextI18n(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invoice_footer_text_i18n')
    language = models.CharField(max_length=2, choices=settings.LANGUAGES)
    invoice_footer_text = models.TextField()

    class Meta:
        unique_together = ('company', 'language')

    def __str__(self):
        return f"Company {self.company_id} [{self.language}] invoice_footer_text"


class CompanyDataProtectionLawTextI18n(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='data_protection_law_text_i18n')
    language = models.CharField(max_length=2, choices=settings.LANGUAGES)
    data_protection_law_text = models.TextField()

    class Meta:
        unique_together = ('company', 'language')

    def __str__(self):
        return f"Company {self.company_id} [{self.language}] data_protection_law_text"


class CompanyBank(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_banks')
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, null=True, blank=True, related_name='company_banks')
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True, related_name='company_banks')
    account_number = models.CharField(max_length=255, null=True, blank=True)
    swift = models.CharField(max_length=255, null=True, blank=True)
    iban = models.CharField(max_length=255, null=True, blank=True)
    is_sepa = models.BooleanField(default=False)
    sepa_cred_identifier = models.CharField(max_length=255, null=True, blank=True)
    barcode_cif = models.CharField(max_length=255, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return "CompanyBank ID {}".format(self.token)


class CompanyBankRouting(models.Model):
    """
    Mapa d'encaminament de remeses SEPA d'una empresa emissora: diu a quin dels
    seus comptes (`company_bank`) s'ha de remesar cada rebut segons l'entitat
    bancària del PAGADOR.

    Cada empresa té el seu mapa. La precedència no es configura, és implícita i
    va de més concret a més general (veure
    `billing/utils/remittance_routing.py::resolve_payment_banks`):

      1. `payer_bank`  — l'entitat del pagador (codi de 4 dígits de l'IBAN,
                         `coredata.Bank.token`) és aquest `bank`.
      2. `foreign`     — l'IBAN del pagador no és espanyol.
      3. `default`     — la resta, i també els rebuts sense IBAN.

    Sense cap fila configurada el comportament no canvia: es remesa tot al
    compte que l'usuari triï a la pantalla de remeses.
    """

    MATCH_PAYER_BANK = 'payer_bank'
    MATCH_FOREIGN = 'foreign'
    MATCH_DEFAULT = 'default'
    MATCH_TYPE_CHOICES = [
        (MATCH_PAYER_BANK, 'Entitat del pagador'),
        (MATCH_FOREIGN, 'IBAN estranger'),
        (MATCH_DEFAULT, 'Per defecte'),
    ]

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='bank_routings')
    company_bank = models.ForeignKey(CompanyBank, on_delete=models.CASCADE, related_name='routings')
    # Només a `payer_bank`: a `foreign` i `default` no hi ha entitat pagadora.
    bank = models.ForeignKey(Bank, on_delete=models.CASCADE, null=True, blank=True, related_name='company_routings')
    match_type = models.CharField(max_length=32, choices=MATCH_TYPE_CHOICES, default=MATCH_PAYER_BANK)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Company Bank Routing"
        verbose_name_plural = "Company Bank Routings"
        constraints = [
            # Una entitat pagadora no pot anar a dos comptes de la mateixa
            # empresa, i només hi pot haver un `foreign` i un `default` per
            # empresa (amb `bank` a NULL, que a Postgres no xoca amb un UNIQUE
            # normal: per això la condició separada).
            models.UniqueConstraint(
                fields=['company', 'bank'],
                condition=models.Q(match_type='payer_bank'),
                name='unique_company_payer_bank_routing',
            ),
            models.UniqueConstraint(
                fields=['company', 'match_type'],
                condition=~models.Q(match_type='payer_bank'),
                name='unique_company_special_routing',
            ),
        ]

    def __str__(self):
        if self.match_type == self.MATCH_PAYER_BANK:
            return f"{self.bank} -> {self.company_bank}"
        return f"{self.get_match_type_display()} -> {self.company_bank}"
 


import os
import uuid
from django.conf import settings



EXPLOITATION_LOGO_TEMP_DIR = 'uploads/exploitation/temp/'
EXPLOITATION_LOGO_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')


def exploitation_logo_upload_to(instance, filename):
    # Nom únic per pujada: amb un nom fix (<id>.jpg) la URL del logo no canviava mai
    # i el navegador continuava servint la imatge cachejada, de manera que semblava
    # que el canvi de logo no s'hagués desat. Qui necessiti el fitxer ha de llegir el
    # camp `logo` (service/utils/exploitation_logo.py), no construir el camí a mà.
    extension = os.path.splitext(filename)[1].lower()
    if extension not in EXPLOITATION_LOGO_EXTENSIONS:
        extension = '.jpg'

    if instance.id:
        return f'uploads/exploitation/{instance.id}/{uuid.uuid4().hex}{extension}'

    # Encara no tenim id: el desem a temp i save() el mou al directori definitiu.
    return f'{EXPLOITATION_LOGO_TEMP_DIR}{uuid.uuid4().hex}{extension}'

class Exploitation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True, blank=True)
    companies = models.ManyToManyField(Company, related_name='exploitations', blank=True)
    cities = models.ManyToManyField(City, related_name='exploitations')
    code = models.CharField(max_length=255, null=True, blank=True)
    accountant_code = models.CharField(max_length=255, null=True, blank=True)
    # Número de concert INCASOL d'aquesta explotació (sense el prefix "S", que l'afegeixen els
    # informes). Si és buit, els informes cauen al ConfigProject global 'incasol_num'.
    incasol_num = models.CharField(max_length=255, null=True, blank=True)
    logo = models.ImageField(upload_to=exploitation_logo_upload_to, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Exploitation"
        verbose_name_plural = "Exploitations"
    
    def save(self, *args, **kwargs):
        previous_logo = None
        if self.pk:
            previous_logo = Exploitation.objects.filter(pk=self.pk).values_list('logo', flat=True).first()

        super().save(*args, **kwargs)

        # En una creació el fitxer ha anat a temp/ perquè encara no teníem id:
        # ara ja el sabem i el movem al directori definitiu de l'explotació.
        if self.logo and self.logo.name.startswith(EXPLOITATION_LOGO_TEMP_DIR):
            new_rel_path = self.logo.name.replace(
                EXPLOITATION_LOGO_TEMP_DIR, f'uploads/exploitation/{self.id}/', 1
            )
            old_path = self.logo.path
            new_full_path = os.path.join(settings.MEDIA_ROOT, new_rel_path)

            if os.path.exists(old_path):
                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                if os.path.exists(new_full_path):
                    os.remove(new_full_path)
                os.rename(old_path, new_full_path)
                self.logo.name = new_rel_path
                # Save just the name change to DB
                super().save(update_fields=['logo'])

        # El nom de fitxer és únic per pujada, així que el logo anterior ja no el
        # referencia ningú i només acumularia brossa al disc.
        current_logo = self.logo.name if self.logo else ''
        if previous_logo and previous_logo != current_logo:
            self.logo.storage.delete(previous_logo)

    def __str__(self):
        if self.name:
            return self.name
        elif self.token:
            return self.token
        else:
            return "Exploitation ID {}".format(self.id)
        
class ExploitationSite(models.Model):
    """Instal·lació germana del mateix client que viu a la seva pròpia URL (desplegaments amb
    una base de dades per explotació). Només serveix per redirigir-hi des del selector
    d'explotació: NO és una Exploitation, no té dades ni cap FK cap a ella, i una taula buida
    deixa el selector tal com és a qualsevol instal·lació normal.
    """
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    # la URL és la identitat d'una instal·lació; el token NO ho és, perquè diverses instal·lacions
    # poden compartir-lo (p. ex. diversos pobles amb el mateix codi postal)
    url = models.URLField(max_length=500, null=True, blank=True, unique=True)
    position = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Exploitation site"
        verbose_name_plural = "Exploitation sites"

    def __str__(self):
        if self.name:
            return self.name
        elif self.token:
            return self.token
        else:
            return "ExploitationSite ID {}".format(self.id)


class DMA(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    code_gis = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.token if self.token else "DMA {}".format(self.id)
    

class Tank(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    volume = models.FloatField(help_text="Volume in cubic meters")
    code_gis = models.CharField(max_length=255, null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.token if self.token else "Tank {}".format(self.id)

class Connection(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    installation_at = models.DateField(null=True, blank=True)
    code_gis = models.CharField(max_length=255, null=True, blank=True)
    flow_rate = models.CharField(max_length=255, null=True, blank=True, help_text="Cabal nominal (m3/h)")
    exploitation = models.ForeignKey(Exploitation, on_delete=models.CASCADE, null=True, blank=True)
    status = models.ForeignKey(ConnectionStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Connection Status")
    type = models.ForeignKey(ConnectionType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Connection Type")
    installation_type = models.ForeignKey(ConnectionInstallationType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Installation Type")
    use_type = models.ForeignKey(ConnectionUseType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Connection Use Type")
    valve_type = models.ForeignKey(ConnectionValveType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Valve Type")
    diameter = models.ForeignKey(ConnectionDiameter, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Diameter")
    material = models.ForeignKey(ConnectionMaterial, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Material")
    tank = models.ForeignKey(Tank, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tank")
    supply_type = models.ForeignKey(SupplyPointSupplyType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SupplyType")
    
    address_street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True, blank=True)
    address_street_number = models.ForeignKey(StreetNumber, on_delete=models.SET_NULL, null=True, blank=True)
    address_postal_code = models.ForeignKey(PostalCode, on_delete=models.SET_NULL, null=True, blank=True)
    address_city =  models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    address_extra = models.TextField(null=True, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    dma = models.ForeignKey(DMA, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Connection"
        verbose_name_plural = "Connections"
        
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Connection ID {}".format(self.id)

def blueprint_upload_to(instance, filename):
    # Genera el camí de càrrega utilitzant l'ID de la connexió
    return f'uploads/blueprints/{instance.connection.id if instance.connection else "0" }/{filename}'

class ConnectionRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, unique=True)
    connection = models.ForeignKey(Connection, on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True)
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, related_name='connection_requests', null=True, blank=True)
    address_billing = models.ForeignKey(PersonAddress, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Connection Billing Address", related_name="connection_requests_billing")
    payment = models.ForeignKey('billing.GeneralPayment', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Connection Payment")
    
    address_street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True, blank=True)
    address_street_number = models.ForeignKey(StreetNumber, on_delete=models.SET_NULL, null=True, blank=True)
    address_postal_code = models.ForeignKey(PostalCode, on_delete=models.SET_NULL, null=True, blank=True)
    address_city =  models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    exploitation = models.ForeignKey(Exploitation, on_delete=models.CASCADE, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    code_gis = models.CharField(max_length=255, null=True, blank=True)
    flow_rate = models.CharField(max_length=255, null=True, blank=True, help_text="Cabal nominal (m3/h)")
    type = models.ForeignKey(ConnectionType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Connection Type")
    installation_type = models.ForeignKey(ConnectionInstallationType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Installation Type")
    use_type = models.ForeignKey(ConnectionUseType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Connection Use Type")
    valve_type = models.ForeignKey(ConnectionValveType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Valve Type")
    diameter = models.ForeignKey(ConnectionDiameter, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Diameter")
    material = models.ForeignKey(ConnectionMaterial, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Material")
    tank = models.ForeignKey(Tank, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tank")
    dma = models.ForeignKey(DMA, on_delete=models.SET_NULL, null=True, blank=True)
    
    status = models.ForeignKey(ConnectionRequestStatus, on_delete=models.SET_NULL, null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    installed_at = models.DateTimeField(null=True, blank=True)
    blueprint = models.FileField(upload_to=blueprint_upload_to, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Connection Request"
        verbose_name_plural = "Connection Requests"
        
    def __str__(self):
        return f"ConnectionRequest {self.token} "
    

def report_file_upload_to(instance, filename):
    # Genera el camí de càrrega utilitzant l'ID de la connexió
    return f'uploads/cluster-reports/{instance.id}/{filename}'

class Cluster(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    status = models.ForeignKey(ClusterStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cluster Status")
    installation_at = models.DateField(null=True, blank=True)
    nb_nozzles = models.IntegerField(null=True, blank=True)
    connection = models.ForeignKey(Connection, related_name='clusters', on_delete=models.CASCADE, null=True, blank=True)
    address_street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True, blank=True)
    address_street_number = models.ForeignKey(StreetNumber, on_delete=models.SET_NULL, null=True, blank=True)
    address_postal_code = models.ForeignKey(PostalCode, on_delete=models.SET_NULL, null=True, blank=True)
    address_city =  models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    report_file = models.FileField(upload_to=report_file_upload_to, null=True, blank=True)
    property = models.ForeignKey('Property', on_delete=models.SET_NULL, null=True, blank=True, related_name='clusters')
    is_potable = models.BooleanField(default=True)
    usage_destination = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Cluster"
        verbose_name_plural = "Clusters"
        
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Cluster ID {}".format(self.id)

class ClusterNozzle(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='nozzles')
    token = models.CharField(max_length=100)
    status = models.ForeignKey(ClusterNozzleStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ClusterNozzle Status")
    type = models.ForeignKey(ClusterNozzleType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="ClusterNozzle Type")
    position = models.IntegerField(null=True, blank=True)
    col = models.IntegerField(null=True, blank=True)
    row = models.IntegerField(null=True, blank=True)
    destination = models.CharField(max_length=255, null=True, blank=True)
    diameter = models.IntegerField(null=True, blank=True)
    def __str__(self):
        return f"{self.cluster.token}"

class RouteZone(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        if self.token:
            return self.token
        else:
            return f"Zona {self.name }"

class Route(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    route_zone = models.ForeignKey(RouteZone, related_name='routes', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="RouteZone")
    reading_batch_template = models.ForeignKey('billing.ReadingBatchTemplate', related_name='routes', on_delete=models.SET_NULL, null=True, blank=True)
    biller = models.ForeignKey('billing.Biller', related_name='routes', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Route"
        verbose_name_plural = "Routes"
        
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Ruta {}".format(self.id)

class RoutePosition(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    route = models.ForeignKey(Route, related_name='positions', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Route")
    position = models.IntegerField(null=True, blank=True)
    notebook = models.CharField(max_length=255, null=True, blank=True)

    reader_observation = models.TextField(null=True, blank=True)

    address_street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True, blank=True)
    address_street_number = models.ForeignKey(StreetNumber, on_delete=models.SET_NULL, null=True, blank=True)
    address_postal_code = models.ForeignKey(PostalCode, on_delete=models.SET_NULL, null=True, blank=True)
    address_city =  models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['route', 'position']),
        ]

    def __str__(self):
        if self.token:
            return self.token
        else:
            return "Ruta Posició {}".format(self.id)


class Meter(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    code = models.CharField(max_length=255, null=True, blank=True)
    code2 = models.CharField(max_length=255, null=True, blank=True)
    is_compound = models.BooleanField(default=False)
    is_property = models.BooleanField(default=False)
    is_general = models.BooleanField(default=False)
    manufacturer = models.CharField(max_length=255, null=True, blank=True)
    manufacturing_year = models.IntegerField(null=True, blank=True)
    model = models.CharField(max_length=255, null=True, blank=True)
    comm_module = models.CharField(max_length=255, null=True, blank=True)
    comm_module_type = models.CharField(max_length=255, null=True, blank=True)
    comm_technology = models.CharField(max_length=255, null=True, blank=True)
    network_provider = models.CharField(max_length=255, null=True, blank=True)
    installation_at = models.DateField(null=True, blank=True)
    uninstallation_at = models.DateField(null=True, blank=True)
    digits = models.IntegerField(default=5, null=True, blank=True)
    caliber = models.ForeignKey(MeterCaliber, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Meter Caliber")
    address_street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True, blank=True)
    address_street_number = models.ForeignKey(StreetNumber, on_delete=models.SET_NULL, null=True, blank=True)
    address_postal_code = models.ForeignKey(PostalCode, on_delete=models.SET_NULL, null=True, blank=True)
    address_city =  models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey(MeterStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Meter Status")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    meter_general = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_meters')
    has_remote_reading = models.BooleanField(default=False)
    force_manual_reading = models.BooleanField(default=False)
    
    REMOTE_READING_TYPE_CHOICES = [
        ('SMART_METERING', 'Smart Metering'),
        ('OTHER', 'Other'),
    ]
    remote_reading_type = models.CharField(max_length=255, choices=REMOTE_READING_TYPE_CHOICES, null=True, blank=True, default='OTHER')
    has_ever_been_remote = models.BooleanField(default=False)


    class Meta:
        verbose_name = "Meter"
        verbose_name_plural = "Meters"
        
    def __str__(self):
        if self.code:
            return self.code
        else:
            return "Meter {}".format(self.id)

class MeterLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='meter_logs')
    field_name = models.TextField(null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    operation_token = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f'MeterLog {self.meter.code}'

class Property(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    cadastral = models.CharField(max_length=255, null=True, blank=True)
    route_position = models.ForeignKey(RoutePosition, related_name='properties', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="RoutePosition")
    
    address_street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True, blank=True)
    address_street_number = models.ForeignKey(StreetNumber, on_delete=models.SET_NULL, null=True, blank=True)
    address_postal_code = models.ForeignKey(PostalCode, on_delete=models.SET_NULL, null=True, blank=True)
    address_city =  models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Property"
        verbose_name_plural = "Properties"
    
    def __str__(self):
        if self.name:
            return self.name
        elif self.token:
            return self.token
        else:
            return "Property {}".format(self.id)
        
class SupplyPoint(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    installation_at = models.DateField(null=True, blank=True)
    cadastral = models.CharField(max_length=255, null=True, blank=True)
    property = models.ForeignKey(Property, related_name='supply_points', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Property")
    type = models.ForeignKey(SupplyPointType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SupplyPoint Type")
    status = models.ForeignKey(SupplyPointStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SupplyPoint Status")
    source = models.ForeignKey(SupplyPointSource, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SupplyPoint Source")
    placement = models.ForeignKey(SupplyPointPlacement, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SupplyPoint Placement")
    supply_type = models.ForeignKey(SupplyPointSupplyType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SupplyPoint SupplyType")
    cluster_nozzle = models.ForeignKey(ClusterNozzle, on_delete=models.SET_NULL, null=True, blank=True, related_name='supply_points')
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, null=True, blank=True, related_name='supply_points')
    meter = models.ForeignKey(Meter, on_delete=models.SET_NULL, null=True, blank=True, related_name='supply_points')

    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='supply_points_address')

    # supply_street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True, blank=True)
    # supply_street_number = models.ForeignKey(StreetNumber, on_delete=models.SET_NULL, null=True, blank=True)
    # supply_postal_code = models.ForeignKey(PostalCode, on_delete=models.SET_NULL, null=True, blank=True)
    
    supply_point_children = models.ManyToManyField('self', blank=True)
    
    is_potable = models.BooleanField(default=True)

    removal_at = models.DateField(null=True, blank=True)
    removal_reason = models.CharField(max_length=255, null=True, blank=True)
    reader_observation = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Supply Point"
        verbose_name_plural = "Supply Points"

    def __str__(self):
        if self.name:
            return self.name
        elif self.token:
            return self.token
        else:
            return "SupplyPoint {}".format(self.id)


class SupplyCutStatus(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    requires_review = models.BooleanField(
        default=False,
        help_text="L'estat entra a quarantena: el tall no s'auto-activa/tanca "
                  "ni toca els punts de subministrament fins que un operari "
                  "l'assigni manualment a un estat vàlid.",
    )

    def __str__(self):
        return self.name if self.name else "SupplyCutStatus ID {}".format(self.token)

class SupplyCutCause(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    is_temporary = models.BooleanField(
        default=False,
        help_text="El tall és puntual (previst amb dates o accidental): NO "
                  "altera l'estat del punt de subministrament ni genera avís "
                  "SMS. Fals = tall indefinit (Impagament, seguretat, ...).",
    )

    def __str__(self):
        return self.name if self.name else "SupplyCutStatus ID {}".format(self.token)

class SupplyCut(models.Model):
    SOURCE_MANUAL = 'manual'
    SOURCE_GISWATER = 'giswater'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_GISWATER, 'Giswater'),
    ]

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    supply_points = models.ManyToManyField(SupplyPoint, blank=True, related_name='supply_cuts')
    status = models.ForeignKey(SupplyCutStatus, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SupplyCut Status")
    cause = models.ForeignKey(SupplyCutCause, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="SupplyCut Cause")

    # Forecast (Giswater forecast_*). This is the date communicated to customers (SMS).
    date_start = models.DateTimeField(
        null=True, blank=True,
        help_text="Previsió d'inici del tall (Giswater forecast_start). Data que es comunica als abonats.",
    )
    date_end = models.DateTimeField(
        null=True, blank=True,
        help_text="Previsió de fi del tall (Giswater forecast_end).",
    )
    # Real execution (Giswater exec_*). Can be empty: a mincut without dates is valid.
    exec_start = models.DateTimeField(
        null=True, blank=True,
        help_text="Inici real del tall (Giswater exec_start). Es seta en arrencar el mincut.",
    )
    exec_end = models.DateTimeField(
        null=True, blank=True,
        help_text="Fi real del tall (Giswater exec_end). Es seta en finalitzar el mincut.",
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
        help_text="Origen del tall. Els de Giswater s'activen/desactiven per exec_*; els manuals, per date_*.",
    )

    is_active = models.BooleanField(default=True)

    # Provenance and review (token alignment with Giswater).
    # `requires_review` quarantines cuts whose Giswater state/cause could not be
    # mapped to a PA catalog row: they are never auto-activated/closed and stay
    # in the admin review queue until manually resolved.
    requires_review = models.BooleanField(
        default=False,
        help_text="Cal revisio manual: l'estat/motiu de Giswater no s'ha pogut "
                  "assignar a cap cataleg del PA.",
    )
    cause_raw = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Ultim valor cru del motiu provinent de Giswater (anl_cause).",
    )
    state_raw = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Ultim valor cru de l'estat provinent de Giswater (state).",
    )
    mincut_state_token = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Token del catàleg d'estat del PA assignat al sincronitzar.",
    )
    mincut_cause_token = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="Token del catàleg de motiu del PA assignat al sincronitzar.",
    )
    
    class Meta:
        verbose_name = "Supply Cut"
        verbose_name_plural = "Supply Cuts"
    
    def __str__(self):
        if self.token:
            return self.token
        else:
            return "SupplyCut {}".format(self.id)

# 
# Taules de suport (observacions)
# 

class SupplyPointObservation(models.Model):
    supply_point = models.ForeignKey(SupplyPoint, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(SupplyPointStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "SupplyPointObservation {}".format(self.id)

class ClusterObservation(models.Model):
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(ClusterStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "ClusterObservation {}".format(self.id)

class ConnectionObservation(models.Model):
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(ConnectionStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "ConnectionObservation {}".format(self.id)


class ConnectionRequestObservation(models.Model):
    connection_request = models.ForeignKey(ConnectionRequest, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(ConnectionRequestStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "ConnectionRequestObservation {}".format(self.id)


class SupplyCutObservation(models.Model):
    supply_cut = models.ForeignKey(SupplyCut, on_delete=models.CASCADE, related_name='observations', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    observation = models.TextField(null=True, blank=True)
    status = models.ForeignKey(SupplyCutStatus, on_delete=models.SET_NULL, null=True, blank=True)
    status_name = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.observation:
            return self.observation
        else:
            return "SupplyCutObservation {}".format(self.id)

class MeterManufacturer(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    
class MeterModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    manufacturer = models.ForeignKey(MeterManufacturer, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)


class ClusterDocumentationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name if self.name else f"ClusterDocumentationType {self.id}"


class ClusterDocumentationFile(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE, related_name='documentation_files', null=True, blank=True)
    file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(ClusterDocumentationType, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"DocumentationFile for cluster {self.cluster.token if self.cluster else self.id}"


class ConnectionDocumentationType(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name if self.name else f"ConnectionDocumentationType {self.id}"


class ConnectionDocumentationFile(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name='documentation_files', null=True, blank=True)
    file = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.ForeignKey(ConnectionDocumentationType, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"DocumentationFile for connection {self.connection.token if self.connection else self.id}"