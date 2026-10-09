from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from datetime import datetime
import random
import datetime

from .models import History
        
@receiver(pre_save, sender=History)
def updateSearchHistory(sender, instance, **kwargs):
    print("SIGNAL")
    print(instance)
    existing_history = History.objects.filter(user=instance.user, found=instance.found, entity=instance.entity)
    for history in existing_history:
        history.delete()
    
    user_history = History.objects.filter(user=instance.user)
    if user_history.count() >= 10:
        oldest_history = user_history.order_by('searched_at')[0]
        oldest_history.delete()

        
        