from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime
import random
import datetime

from .models import LineItemType, PriceInterval, PriceVariableInterval

@receiver(post_save, sender=LineItemType)
def delete_incorrect_intervals(sender, instance, **kwargs):
    if instance.id:
        price_intervals = PriceInterval.objects.filter(token=('' or None))
        price_variable_intervals = PriceVariableInterval.objects.filter(token=('' or None))
        for interval in price_intervals:
            interval.delete()
        for interval in price_variable_intervals:
            interval.delete()
        
        
        