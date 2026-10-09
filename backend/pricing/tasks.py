import datetime
from celery import shared_task
from django.utils import timezone
from .models import BillingRange, PriceRate

@shared_task
def set_active_billing_range():
    # ??????
    """ now = timezone.now().date()
    billing_range_start_today = BillingRange.objects.filter(start__lte=now)
    for billing_range in billing_range_start_today:
        if billing_range.price_rate: 
            if billing_range.price_rate.billing_range_active:
                billing_range.price_rate.billing_range_active.end = now
                billing_range.price_rate.billing_range_active.save()
            
            billing_range.price_rate.billing_range_active = billing_range
            billing_range.price_rate.save() """
        
        
        
