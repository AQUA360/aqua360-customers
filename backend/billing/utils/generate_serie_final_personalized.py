
"""
Plantilla per personalitzar la generació de serie_final per client.

Si aquest fitxer existeix dins de billing.utils, invoice_service farà servir
generate_serie_final d'aquí en lloc de la implementació per defecte.
"""
from django.db import transaction
from django.db.models import Max

from billing.models import Invoice, InvoiceSequence

def generate_serie_final(serie_token, date_str, invoice_type=None, exclude_status_token=None, invoice=None):
    """Personalitzeu la lògica de generació de serie_final aquí.
    invoice: la factura (Invoice) per accedir a exploitation.token, etc.
    """
    exploitation_token = invoice.exploitation.token if invoice and getattr(invoice, 'exploitation', None) else None
    sequence_prefix = f"{serie_token}"
    # La sèrie fa servir ym (2610). Si la factura porta issue_date, la data surt d'allà.
    if invoice and getattr(invoice, 'issue_date', None):
        date_str = invoice.issue_date.strftime('%y%m')
    elif date_str and len(date_str) >= 4:
        date_str = date_str[2:]
    if exploitation_token:
        # token és un CharField; :02d només funciona amb enters.
        exploitation_code = str(exploitation_token).zfill(2)
        sequence_prefix = f"{sequence_prefix}/{exploitation_code}{date_str}"
    else:
        sequence_prefix = f"{sequence_prefix}/{date_str}"
        
    # if invoice_type:
    #    sequence_prefix = f"{sequence_prefix}/{invoice_type}"
    
    with transaction.atomic():
        seq = InvoiceSequence.objects.select_for_update().filter(prefix=sequence_prefix).first()
        if seq is None:
            qs = Invoice.objects.filter(
                serie_final__startswith=sequence_prefix + "/",
            ).exclude(serie_final__isnull=True).exclude(serie_final="")
            if invoice_type:
                qs = qs.filter(type_final=invoice_type)
            if exclude_status_token:
                qs = qs.exclude(status__token=exclude_status_token)
            max_serie = qs.aggregate(max_serie=Max('serie_final'))['max_serie']
            start_from = 0
            if max_serie:
                try:
                    last_part = max_serie.split('/')[-1]
                    start_from = int(last_part)
                except (ValueError, IndexError):
                    start_from = 0
            seq = InvoiceSequence.objects.create(prefix=sequence_prefix, last_number=start_from)

        seq.last_number = seq.last_number + 1
        next_num = seq.last_number
        seq.save(update_fields=['last_number'])
        return f"{sequence_prefix}/{next_num:06d}"
        
   
