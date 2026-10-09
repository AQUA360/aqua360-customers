from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from coredata.models import ConfigProject, Street, Address
from coredata.utils.iban_validator_utils import get_spanish_bank_code_candidates
from .models import PersonBank, Bank
import time

import uuid
from contract.middleware import get_current_user
from coredata.models import Person, PersonLog

@receiver(pre_save, sender=Street)
def street_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_street_data = Street.objects.get(pk=instance.pk)
        except Street.DoesNotExist:
            instance._old_street_data = None
    else:
        instance._old_street_data = None

@receiver(post_save, sender=Street)
def street_post_save(sender, instance, created, **kwargs):
    if not created and hasattr(instance, '_old_street_data') and instance._old_street_data:
        old = instance._old_street_data
        if old.name != instance.name or old.name_2 != instance.name_2 or old.type != instance.type:
            # Update all related addresses
            addresses = Address.objects.filter(street=instance)
            for address in addresses:
                address.save()

@receiver(post_save, sender=PersonBank)
def assign_bank(sender, instance, **kwargs):
    if hasattr(instance, '_skip_signal'):
        return  
    elif instance.id:
        try:
            if instance.iban:
                country_code = instance.iban[0:2]
                if country_code.upper() == 'ES':
                    bank_code = instance.iban[4:8]
                    bank = Bank.objects.filter(token__in=get_spanish_bank_code_candidates(bank_code)).first()
                    if bank:
                        instance.bank = bank
                        instance._skip_signal = True
                        instance.save()
            
        except Exception as exception:
            return

@receiver(pre_save, sender=Person)
def person_pre_save(sender, instance, **kwargs):
    if instance.pk:  # This is an update
        try:
            old_instance = Person.objects.get(pk=instance.pk)
            current_user = get_current_user()

            if not current_user or getattr(current_user, "is_anonymous", False):
                from django.contrib.auth import get_user_model
                User = get_user_model()
                current_user = User.objects.order_by("id").first()

            operation_token = str(uuid.uuid4())

            # Excloem updated_at: canvia a cada save i no aporta informació útil
            fields = [f.name for f in Person._meta.fields if f.name != 'updated_at']

            for field in fields:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)

                if old_value != new_value:
                    old_value_str = str(old_value) if old_value is not None else None
                    new_value_str = str(new_value) if new_value is not None else None

                    PersonLog.objects.create(
                        person=instance,
                        field_name=field,
                        old_value=old_value_str,
                        new_value=new_value_str,
                        operation_token=operation_token,
                        user=current_user
                    )
        except Person.DoesNotExist:
            pass            