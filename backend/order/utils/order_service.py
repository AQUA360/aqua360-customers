import datetime
import logging
from django.conf import settings
from logger.models import LogContractChange
from ..models import Order, OrderStatus, OrderType
from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject

logger = logging.getLogger(__name__)

#set completed_at to order
def order_complete(user, order_id):
    print("completing order")
    order = Order.objects.get(id=order_id)
    print(order.id)
    
    order.completed_at = datetime.datetime.now()
    order.save()
    
    # logger

    return order

def order_invalidate(user, order_id):
    order = Order.objects.get(id=order_id)
    
    if settings.RABBITMQ_ENABLED:
        config = ConfigProject.objects.filter(
            token="sent_order_status_token"
        ).first()
        if config:
            sent_status_token = config.value
        else:
            logger.warning(
                "ConfigProject for 'sent_order_status_token' not found. Using '-5' as default. This may not work well."
            )
            sent_status_token = "-5"
        
        try:
            sent_status = OrderStatus.objects.get(token=sent_status_token)
            order.status = sent_status
            order.save()
        except OrderStatus.DoesNotExist:
            logger.error(f"OrderStatus with token {sent_status_token} not found.")
            
    return order