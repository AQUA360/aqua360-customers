from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
import uuid
from verifactu.models import VerifactuNotification, VerifactuNotificationLog
from contract.middleware import get_current_user


@receiver(post_save, sender=VerifactuNotification)
def create_verifactu_notification_log(sender, instance, created, **kwargs):
    if created:
        try:
            current_user = get_current_user()
            # Allow None user - logs are still valuable for tracking
            operation_token = str(uuid.uuid4())
            VerifactuNotificationLog.objects.create(
                verifactu_notification=instance,
                field_name='Created',
                new_value='True',
                operation_token=operation_token,
                user=current_user if current_user and not current_user.is_anonymous else None
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating VerifactuNotificationLog on creation: {e}")
            import traceback
            logger.error(traceback.format_exc())

@receiver(pre_save, sender=VerifactuNotification)
def verifactu_notification_pre_save(sender, instance, **kwargs):
    if instance.pk:  # This is an update
        try:
            old_instance = VerifactuNotification.objects.get(pk=instance.pk)
            current_user = get_current_user()
            # Allow None user - logs are still valuable for tracking
            operation_token = str(uuid.uuid4())
            
            fields = [f.name for f in VerifactuNotification._meta.fields]
            
            for field in fields:
                old_value = getattr(old_instance, field)
                new_value = getattr(instance, field)
                
                if old_value != new_value:
                    old_value_str = str(old_value) if old_value is not None else None
                    new_value_str = str(new_value) if new_value is not None else None
                    
                    VerifactuNotificationLog.objects.create(
                        verifactu_notification=instance,
                        field_name=field,
                        old_value=old_value_str,
                        new_value=new_value_str,
                        operation_token=operation_token,
                        user=current_user if current_user and not current_user.is_anonymous else None
                    )
        except VerifactuNotification.DoesNotExist:
            pass
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating VerifactuNotificationLog on update: {e}")
            pass
