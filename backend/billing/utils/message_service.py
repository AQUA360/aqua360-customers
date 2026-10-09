from django.utils import timezone

from billing.utils.charts_service import generate_chart
from ..models import Invoice, Message, MessageCondition, InvoiceTemplate

def invoice_add_messages(invoice, hide_background_and_logos=False):
    now = timezone.now().date()
    invoice_origin = invoice.origin
    try:
        template = InvoiceTemplate.objects.filter(origin=invoice_origin).first()
    except InvoiceTemplate.DoesNotExist:
        return {}
    charts = {}
    messages = Message.objects.filter(template=template)
    
    for message in messages:
        chart = None
        try:
            if message.message_type == 'GRAPHIC':
                chart = generate_chart(invoice, message.title, hide_background_and_logos=hide_background_and_logos)
                charts[message.id] = chart
        except:
            pass
        
        if (message.start_at and message.end_at) and (now < message.start_at or now > message.end_at):
            continue
        elif message.start_at and now < message.start_at:
            continue
        elif message.end_at and now > message.end_at:
            continue
        message_eval_conditions(message, invoice)
    
    message_data = {}
    for message in messages:
        if invoice in message.invoices.all():
            message_data[message.id] = {
                "title": message.title,
                "content": message.content,
                "chart": charts.get(message.id, None) 
            }
    
    return message_data

def message_eval_conditions(message, invoice):
    contract = None
    if invoice.contract:
        contract = invoice.contract
    elif invoice.contract_request:
        contract = invoice.contract_request
    elif invoice.contract_termination:
        contract = invoice.contract_termination.contract
    variables = generate_message_variables(message, invoice, contract)
    
    if not message.conditions.exists():
        message.invoices.add(invoice)
        message.save()
        return
    
    for condition in message.conditions.all().order_by('position'):
        quantity_key = condition.quantity['value']
        
        if condition.quantity['value'] in variables:
            quantity_value = variables[quantity_key]
            if condition.operation == 'is_null':
                if condition.quantity['value'] in variables:
                    if quantity_value is None:
                        message.invoices.add(invoice)
                        message.save()
                        return
                    
            if condition.operation == 'is_true':
                if quantity_value:
                    message.invoices.add(invoice)
                    message.save()
        return
        
def generate_message_variables(message, invoice, contract):
    variables = {
        'contract.contacts': contract.contacts if contract.contacts else None,
        'reading.is_estimated': any(reading.is_estimated for reading in invoice.readings.all()) if invoice.readings.exists() else None,
    }
    
    return variables