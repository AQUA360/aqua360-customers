from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from logger.models import LogIncidentStatusChange
from notification.models import Incident, Notification

@receiver(pre_save, sender=Incident)
def detect_status_change(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if previous.status_id == instance.status_id:
        return
    
    # Data de tancament i pausa del termini segons el nou estat
    from notification.utils.incident_utils import apply_status_change
    apply_status_change(instance, previous.status)
    
    # L'usuari el posa el serialitzador que desa el canvi
    user = getattr(instance, '_change_user', None)
    
    # Create a LogOrderStatus object
    LogIncidentStatusChange.objects.create(
        object=instance,
        previous_status=previous.status,
        current_status=instance.status,
        observation=f"Status changed from {previous.status.name if previous.status else '-'} to {instance.status.name if instance.status else '-'}",
        user=user
    )


@receiver(post_save, sender=Notification)
def create_notification(sender, instance, **kwargs):
    try:
        if instance.user is not None:
            user_notifications = Notification.objects.filter(user=instance.user, archived_by__isnull=True)
            if user_notifications.count() > 20:
                ids_to_delete = list(user_notifications.order_by('-created_at')[20:].values_list('id', flat=True))
                Notification.objects.filter(id__in=ids_to_delete).delete()
        else:
            general_notifications = Notification.objects.filter(user__isnull=True, archived_by__isnull=True)
            if general_notifications.count() > 20:
                ids_to_delete = list(general_notifications.order_by('-created_at')[20:].values_list('id', flat=True))
                Notification.objects.filter(id__in=ids_to_delete).delete()
    except Exception as e:
        print(f"Error cleaning notifications: {e}")