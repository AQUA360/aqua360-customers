from urllib.request import Request
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
    if previous.status.id == instance.status.id:
        return
    
    request = None
    if hasattr(sender, 'request') and isinstance(sender.request, Request):
        request = sender.request
    elif hasattr(instance, '_request') and isinstance(instance._request, Request):
        request = instance._request
    user = None
    
    if request and request.user and request.user.is_authenticated:
        user = request.user
    
    if user is None:
        print("No authenticated user found.")
    
    print(f"Incident {instance.pk} status changed from {previous.status.name} to {instance.status.name}")
    
    # Create a LogOrderStatus object
    LogIncidentStatusChange.objects.create(
        object=instance,
        previous_status=previous.status,
        current_status=instance.status,
        observation=f"Status changed from {previous.status.name} to {instance.status.name}",
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