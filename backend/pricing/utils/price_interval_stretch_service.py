import os
from logger.models import LogContractChange
from ..models import PriceIntervalStretch, PriceVariableIntervalStretch
from coredata.models import ConfigProject

#Order price interval stretches
def price_interval_stretch_order(user, new_stretch_id, isCreating):
    new_price_interval_stretch = PriceIntervalStretch.objects.get(id=new_stretch_id)
    price_interval = new_price_interval_stretch.price_interval
    price_interval_stretches = PriceIntervalStretch.objects.filter(price_interval=price_interval)
    
    if isCreating:
        for stretch in price_interval_stretches:
            
            if stretch and new_price_interval_stretch.end_stretch < stretch.end_stretch:
                stretch.stretch += 1
                stretch.save()
            elif stretch and new_price_interval_stretch.end_stretch > stretch.end_stretch:
                new_price_interval_stretch.stretch += 1
                new_price_interval_stretch.save()
    else:
        for stretch in price_interval_stretches:
            if stretch.id != new_stretch_id:
                if new_price_interval_stretch.end_stretch < stretch.end_stretch:
                    stretch.stretch += 1
                elif new_price_interval_stretch.end_stretch > stretch.end_stretch:
                    stretch.stretch -= 1
                stretch.save()

        stretch_order = 1
        for stretch in price_interval_stretches.order_by('end_stretch'):
            stretch.stretch = stretch_order
            stretch_order += 1
            stretch.save()
            
def variable_prixed_price_interval_stretch_order(user, new_stretch_id, isCreating):
    new_price_interval_stretch = PriceVariableIntervalStretch.objects.get(id=new_stretch_id)
    price_interval = new_price_interval_stretch.price_variable_interval
    price_interval_stretches = PriceVariableIntervalStretch.objects.filter(price_variable_interval=price_interval)
    
    if isCreating:
        for stretch in price_interval_stretches:
            
            if stretch and new_price_interval_stretch.end_stretch < stretch.end_stretch:
                stretch.stretch += 1
                stretch.save()
            elif stretch and new_price_interval_stretch.end_stretch > stretch.end_stretch:
                new_price_interval_stretch.stretch += 1
                new_price_interval_stretch.save()
    else:
        for stretch in price_interval_stretches:
            if stretch.id != new_stretch_id:
                if new_price_interval_stretch.end_stretch < stretch.end_stretch:
                    stretch.stretch += 1
                elif new_price_interval_stretch.end_stretch > stretch.end_stretch:
                    stretch.stretch -= 1
                stretch.save()

        stretch_order = 1
        for stretch in price_interval_stretches.order_by('end_stretch'):
            stretch.stretch = stretch_order
            stretch_order += 1
            stretch.save()
            
 
    