from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from django.db.models import Count
import logging
from billing.models import Invoice
from coredata.utils.name_utils import generate_token
from verifactu.models import VerifactuBatch, VerifactuNotification
from verifactu.utils.notify_verifactu_service import notify_invoices
from verifactu.utils.qr_url_helper import generate_verifactu_url
from verifactu.utils.hash_key_service import sha256_hex
from decouple import config

logger = logging.getLogger(__name__)


def create_verifactu_invoice(invoice: Invoice, single_batch: bool = False) -> VerifactuNotification:
    # print("\033[95mCreating verifactu invoice, single_batch:", single_batch, "\033[0m")
    
    if not config('VERIFACTU_ENABLED', default=False, cast=bool):
        return None
    
    verifactu_url = generate_verifactu_url(invoice.serie_final, invoice.issue_date, invoice.total_final)
    
    # Generate FechaHoraHusoGenRegistro in format: '2024-09-13T19:20:30+01:00'
    now = datetime.now(ZoneInfo('Europe/Madrid'))
    fecha_hora_huso_gen_registro = now.strftime('%Y-%m-%dT%H:%M:%S%z')
    # Format timezone offset from +0100 to +01:00 (insert colon before last 2 digits)
    fecha_hora_huso_gen_registro = fecha_hora_huso_gen_registro[:-2] + ':' + fecha_hora_huso_gen_registro[-2:]
    nif = config('VERIFACTU_NIF')
    if not nif:
        return None

    previous_verifactu_notification = VerifactuNotification.objects.order_by('-id').first()
    if previous_verifactu_notification:
        hash_Huella = previous_verifactu_notification.verifactu_hash
    else:
        hash_Huella = None

    # Calculate cuota_total safely, handling None values
    total_final = invoice.total_final if invoice.total_final is not None else 0
    subtotal_final = invoice.subtotal_final if invoice.subtotal_final is not None else 0
    cuota_total = total_final - subtotal_final

    verifactu_hash = sha256_hex(
        id_emisor_factura=nif,
        num_serie_factura=invoice.serie_final,
        fecha_expedicion_factura=invoice.issue_date.strftime('%d-%m-%Y'),
        tipo_factura='F1',
        cuota_total=str(cuota_total),
        importe_total=str(invoice.total_final) if invoice.total_final is not None else '0',
        huella=hash_Huella,
        fecha_hora_huso_gen_registro=fecha_hora_huso_gen_registro
    )
    
    if single_batch:
        verifactu_batch = VerifactuBatch.objects.create(
            token=generate_token(VerifactuBatch),
            action='Alta',
        )
    else:
        # Try to get a VerifactuBatch that has < 1,000 verifactu_invoices and has not been sent
        verifactu_batch = VerifactuBatch.objects.filter(
            sent_at__isnull=True
        ).annotate(
            invoice_count=Count('verifactu_invoices')
        ).filter(
            invoice_count__lt=1000
        ).first()
        
        # If there is none, create a new batch
        if not verifactu_batch:
            verifactu_batch = VerifactuBatch.objects.create(
                token=generate_token(VerifactuBatch),
                action='Alta',
            )
    
    verifactu_notification = VerifactuNotification.objects.create(
        token=generate_token(VerifactuNotification),
        invoice=invoice,
        verifactu_hash=verifactu_hash,
        verifactu_qr=verifactu_url,
        hash_IDEmisor=nif,
        hash_NumSerie=invoice.serie_final,  
        hash_FechaExpedicion=invoice.issue_date.strftime('%d-%m-%Y'),
        hash_TipoFactura='F1',
        hash_CuotaTotal=str(cuota_total),
        hash_ImporteTotal=str(invoice.total_final) if invoice.total_final is not None else '0',
        hash_Huella=hash_Huella,
        hash_FechaHoraHusoGenRegistro=fecha_hora_huso_gen_registro,
        
        verifactu_previous_notification=previous_verifactu_notification,
        batch=verifactu_batch
    )
    invoice.verifactu_notification = verifactu_notification
    
    invoice._skip_signal_updating_verifactu = True
    invoice.save()
    del invoice._skip_signal_updating_verifactu
    
    if single_batch:
        try:
            notify_invoices([invoice], verifactu_batch)
        except Exception as e:
            # Log the error but don't fail invoice creation
            logger.error(f"Error notifying Verifactu for invoice {invoice.id}: {str(e)}")
            logger.error("Invoice and VerifactuNotification were created successfully, but notification failed.")
    else:
        # Check if batch has 200 invoices (after adding the new one)
        notification_count = verifactu_batch.verifactu_notifications.count()
        if notification_count == 200:
            # Get all invoices in this batch
            batch_invoices = Invoice.objects.filter(verifactu_notification__batch=verifactu_batch)
            try:
                notify_invoices(list(batch_invoices), verifactu_batch)
            except Exception as e:
                # Log the error but don't fail invoice creation
                logger.error(f"Error notifying Verifactu for batch {verifactu_batch.id}: {str(e)}")
                logger.error("Batch reached 200 invoices but notification failed.")
    
    return verifactu_notification

def notify_verifactu_unsent_batches():
    verifactu_batches = VerifactuBatch.objects.filter(sent_at__isnull=True)
    for verifactu_batch in verifactu_batches:
        batch_invoices = Invoice.objects.filter(verifactu_notification__batch=verifactu_batch)
        notify_invoices(list(batch_invoices), verifactu_batch)
        
def cancel_verifactu_invoice(invoice: Invoice) -> VerifactuNotification:
    verifactu_notification = invoice.verifactu_notification
    if verifactu_notification:
        verifactu_notification.invoice_cancelled = True
        verifactu_notification.cancelled_at = datetime.now()
        verifactu_notification.save()
    return verifactu_notification