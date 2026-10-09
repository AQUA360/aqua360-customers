"""
Test script for sending example SOAP XML message to Verifactu service.

This script sends the example "alta inicial" (initial registration) message
as specified in the Verifactu documentation.
"""

from datetime import datetime
import logging
from billing.models import Invoice
from verifactu.models import VerifactuBatch
from verifactu.utils.soap_client_service import VerifactuSOAPClient, VerifactuSOAPFault, VerifactuSOAPTransportError
from django.conf import settings
from decouple import config
from verifactu.models import VerifactuNotification, VerifactuNotificationLog
from contract.middleware import get_current_user
import uuid
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

    
def build_invoices_data_body(invoices: list[Invoice]):
    """
    Build the data body for the invoices
    
    """
    
    nif = config('VERIFACTU_NIF')
    if not nif:
        return None
    
    registrofacturas = []
    for invoice in invoices:
        desglose = []
        
        cuota_total = invoice.total_final - invoice.subtotal_final
        
        for line_item in invoice.line_items.all():
            # Format TipoImpositivo as Decimal(3,2) - always 2 decimal places (e.g., "21.00", "10.00")
            tax_percent = line_item.tax_percent if line_item.tax_percent is not None else 0
            tipo_impositivo = f"{float(tax_percent):.2f}"
            
            # BaseImponibleOimporteNoSujeto: base amount before tax (price field)
            base_imponible = line_item.price if line_item.price is not None else 0
            base_imponible_str = f"{float(base_imponible):.2f}"
            
            # CuotaRepercutida: tax amount (tax_price field)
            cuota_repercutida = line_item.tax_price if line_item.tax_price is not None else 0
            cuota_repercutida_str = f"{float(cuota_repercutida):.2f}"
            detalle_desglose = {
                'ClaveRegimen': '01',
                'BaseImponibleOimporteNoSujeto': base_imponible_str
            }
            
            
            if tax_percent == 0:
                detalle_desglose['CalificacionOperacion'] = 'N1'
            else:
                detalle_desglose['CalificacionOperacion'] = 'S1'
                detalle_desglose['TipoImpositivo'] = tipo_impositivo
                detalle_desglose['CuotaRepercutida'] = cuota_repercutida_str
            
            desglose.append(detalle_desglose)
        
        verifactu_data = invoice.verifactu_notification
        
        encadenamiento = {}
        
        if verifactu_data.verifactu_previous_notification:
            encadenamiento = {
                'RegistroAnterior': {
                    'IDEmisorFactura': nif,
                    'NumSerieFactura': verifactu_data.verifactu_previous_notification.hash_NumSerie,
                    'FechaExpedicionFactura': verifactu_data.verifactu_previous_notification.hash_FechaExpedicion,
                    'Huella': verifactu_data.hash_Huella
                }
            }
        else:
            encadenamiento = {
                'PrimerRegistro': 'S'
            }
        
        
        if invoice.customer_token_final != '99999999R' and invoice.customer_token_final is not None:
            destinatarios = {
                'IDDestinatario': {
                    'NombreRazon': invoice.customer_final,
                    'NIF': invoice.customer_token_final
                }
            }
        else:
            destinatarios = {
                'IDDestinatario': {
                    'NombreRazon': invoice.customer_final,
                    'IDOtro': {
                        'IDType': '07',
                        'CodigoPais': 'ES',
                        'ID': '99999999R'
                    }
                }
            }
            
        tipofactura = 'F1'
        if invoice.simplified or invoice.customer_token_final == None or invoice.customer_token_final == '':
            tipofactura = 'F2'
        
        registrofacturas.append({
                'RegistroAlta': {
                    'IDVersion': '1.0',
                    'IDFactura': {
                        'IDEmisorFactura': nif,
                        'NumSerieFactura': invoice.serie_final,
                        'FechaExpedicionFactura': invoice.issue_date.strftime('%d-%m-%Y')
                    },
                    'NombreRazonEmisor': config('VERIFACTU_NAME', default=''),
                    'TipoFactura': tipofactura,
                    'DescripcionOperacion': invoice.title_final,
                    'Destinatarios': destinatarios,
                    'Desglose': {
                        'DetalleDesglose': desglose
                    },
                    'CuotaTotal': str(cuota_total) if cuota_total is not None else '0',
                    'ImporteTotal': str(invoice.total_final) if invoice.total_final is not None else '0',
                    'Encadenamiento': encadenamiento,
                    'SistemaInformatico': dict(settings.VERIFACTU_SISTEMA_INFORMATICO),
                    'FechaHoraHusoGenRegistro': verifactu_data.hash_FechaHoraHusoGenRegistro,
                    'TipoHuella': '01',
                    'Huella': verifactu_data.verifactu_hash
                }
            })
    data_body = {
        'Cabecera': {
            'ObligadoEmision': {
                'NombreRazon': config('VERIFACTU_NAME', default=''),
                'NIF': nif
            }
        },
        'RegistroFactura': registrofacturas
    }
    return data_body

def build_consultation_data(ejercicio=2024, periodo=9):
    periodo_str = f"{periodo:02d}"  # Format as 2-digit string with zero padding
    return {
        'Cabecera': {
            'IDVersion': '1.0',
            'ObligadoEmision': {
                'NombreRazon': config('VERIFACTU_NAME', default=''),
                'NIF': config('VERIFACTU_NIF', default='')
            }
        },
        'FiltroConsulta': {
            'PeriodoImputacion': {
                'Ejercicio': str(ejercicio),
                'Periodo': periodo_str
            }
        }
    }

def notify_cancelled_invoices(invoices: list[Invoice]):
    """
    Notify the cancelled invoices to the Verifactu service
    """
    logger.info("=" * 80)
    logger.info("Notifying cancelled invoices to verifactu")
    logger.info("=" * 80)

        

def notify_invoices(invoices: list[Invoice], batch: VerifactuBatch):
    """
    Test function to send the example invoice registration message.
    
    This function:
    1. Builds the invoice data structure
    2. Initializes the SOAP client
    3. Sends the message to the Verifactu service
    4. Handles errors appropriately
    """
    try:
        logger.info("=" * 80)
        logger.info("Sending invoice to verifactu")
        logger.info("=" * 80)
        
        # Initialize the SOAP client
        logger.info("Initializing SOAP client...")
        client = VerifactuSOAPClient()
        
        # Get WSDL info to find the correct operation name
        # logger.info("Getting WSDL information...")
        wsdl_info = client.get_wsdl_info()
        # logger.info(f"Target Namespace: {wsdl_info['target_namespace']}")
        logger.info(f"Available operations: {list(set(op['name'] for op in wsdl_info['operations']))}")
        
        # Try to find the correct operation name
        # Common operation names for Verifactu:
        operation_names = [
            'RegFactuSistemaFacturacion',
            'ConsultaFactuSistemaFacturacion',
        ]
        
        # Find the first matching operation
        available_ops = list(set(op['name'] for op in wsdl_info['operations']))
        operation_name = None
        
        for op_name in operation_names:
            if op_name in available_ops:
                operation_name = op_name
                break
        
        if not operation_name:
            logger.warning(f"Could not find expected operation. Available operations: {available_ops}")
            logger.info("Trying with first available operation...")
            if available_ops:
                operation_name = available_ops[0]
            else:
                logger.error("No operations found in WSDL!")
                return
        
        logger.info(f"Using operation: {operation_name}")
        
        logger.info("Sending SOAP request...")
        
        # Build the invoice data
        xml_data = build_invoices_data_body(invoices)
        operation_name = 'RegFactuSistemaFacturacion'
        logger.info("Invoice data structure built successfully")
        
        # return None
        
        batch.sent_at = datetime.now()
        batch.save(update_fields=['sent_at'])
        
        print("*"*100)
        print(operation_name)
        print(xml_data)
        print("*"*100)
        
        # Send the SOAP request        
        # Call the service
        response = client.call_service(
            operation_name=operation_name,
            **xml_data  # Unpack the invoice data as keyword arguments
        )
        
        
        if response:
            batch.response = str(response)
            batch.response_status = response.get('EstadoEnvio')
            batch.save(update_fields=['response', 'response_status'])
            logger.info('')
            logger.info("\033[92mTest completed successfully!\033[0m")
            logger.info('')
            logger.info("\033[93mResponse received:\033[0m")
            logger.info(str(response))
            
            responseStatus = response.get('EstadoEnvio')
        
            logger.info(f"\033[93mSOAP request completed\033[0m")
            if responseStatus == 'Correcto':
                logger.info("\033[92mSOAP request completed successfully!\033[0m")
            elif responseStatus == 'ParcialmenteCorrecto':
                logger.info("\033[93mSOAP request completed partially successfully!\033[0m")
            elif responseStatus == 'Incorrecto':
                logger.info("\033[91mSOAP request completed with errors!\033[0m")

            # Handle response - convert to dict if needed
            if not isinstance(response, dict):
                try:
                    import json
                    if hasattr(response, '__dict__'):
                        response = response.__dict__
                    elif isinstance(response, str):
                        import ast
                        response = ast.literal_eval(response)
                except Exception as e:
                    logger.warning(f"Could not convert response to dict: {e}")
                    response = {}
            
            response_lines = response.get('RespuestaLinea', [])
            
            if response_lines:
                # Collect all series numbers and their response data first
                series_data_map = {}
                for line in response_lines:
                    try:
                        # Handle both dict and object-like responses
                        if not isinstance(line, dict):
                            line = dict(line) if hasattr(line, '__dict__') else {}
                        
                        id_data = line.get('IDFactura', {})
                        if not isinstance(id_data, dict):
                            id_data = dict(id_data) if hasattr(id_data, '__dict__') else {}
                        
                        serie = id_data.get('NumSerieFactura')
                        if serie:
                            estado_registro = line.get('EstadoRegistro')
                            series_data_map[serie] = {
                                'response_status': estado_registro,
                                'message': None
                            }
                            # Set error message if status is not 'Correcto'
                            if estado_registro != 'Correcto':
                                codigo_error = line.get('CodigoErrorRegistro', '')
                                descripcion_error = line.get('DescripcionErrorRegistro', '')
                                series_data_map[serie]['message'] = f"{codigo_error} - {descripcion_error}".strip(' - ')
                    except Exception as e:
                        logger.error(f"Error processing response line: {e}")
                        logger.error(f"Line data: {line}")

                # Bulk fetch all invoices with their verifactu_invoices in a single query
                series_list = list(series_data_map.keys())
                if series_list:
                    invoices = Invoice.objects.filter(
                        serie_final__in=series_list
                    ).select_related('verifactu_notification')

                    # Update verifactu_invoices
                    verifactu_invoices_to_update = []
                    verifactu_invoice_logs = []
                    
                    current_user = get_current_user()
                    # Allow None user - logs are still valuable for tracking
                    operation_token = str(uuid.uuid4())
                    user_for_log = current_user if current_user and not current_user.is_anonymous else None
                    
                    for invoice in invoices:
                        if invoice.verifactu_notification and invoice.serie_final in series_data_map:
                            data = series_data_map[invoice.serie_final]
                            old_response_status = invoice.verifactu_notification.response_status
                            old_message = invoice.verifactu_notification.message
                            
                            invoice.verifactu_notification.response_status = data['response_status']
                            # Always update message - set to None if status is 'Correcto', otherwise set the error message
                            invoice.verifactu_notification.message = data['message']
                            verifactu_invoices_to_update.append(invoice.verifactu_notification)
                            
                            # Prepare logs for bulk_update (which doesn't trigger signals)
                            # Always log response_status change
                            if old_response_status != data['response_status']:
                                verifactu_invoice_logs.append(
                                    VerifactuNotificationLog(
                                        verifactu_notification=invoice.verifactu_notification,
                                        field_name='response_status',
                                        old_value=str(old_response_status) if old_response_status else None,
                                        new_value=str(data['response_status']) if data['response_status'] else None,
                                        operation_token=operation_token,
                                        user=user_for_log
                                    )
                                )
                                logger.info(f"Prepared log for response_status change: {old_response_status} -> {data['response_status']}")
                            # Always log message change
                            if old_message != data['message']:
                                verifactu_invoice_logs.append(
                                    VerifactuNotificationLog(
                                        verifactu_notification=invoice.verifactu_notification,
                                        field_name='message',
                                        old_value=str(old_message) if old_message else None,
                                        new_value=str(data['message']) if data['message'] else None,
                                        operation_token=operation_token,
                                        user=user_for_log
                                    )
                                )
                    
                    # Bulk update all verifactu_invoices at once
                    if verifactu_invoices_to_update:
                        VerifactuNotification.objects.bulk_update(
                            verifactu_invoices_to_update,
                            ['response_status', 'message'],
                            batch_size=100
                        )
                        
                        # Create logs manually since bulk_update doesn't trigger signals
                        if verifactu_invoice_logs:
                            VerifactuNotificationLog.objects.bulk_create(verifactu_invoice_logs, batch_size=100)
                        else:
                            logger.warning(f"No logs to create. Check if fields actually changed or if user/token is missing.")
                    else:
                        logger.warning("No verifactu_invoices to update - check if invoices have verifactu_invoice relationship")
                else:
                    logger.warning("No series found in response lines")
            else:
                logger.warning("No response lines found in response")
            
        else:
            batch.response = "Error, no response received"
            batch.response_status = "Error"
            batch.save(update_fields=['response', 'response_status'])

        return response
        
    except VerifactuSOAPFault as e:
        batch.response = "Error, no response received"
        batch.response_status = "Error"
        batch.save(update_fields=['response', 'response_status'])
        logger.error("=" * 80)
        logger.error("SOAP FAULT RECEIVED")
        logger.error("=" * 80)
        logger.error(f"Message: {e.message}")
        logger.error(f"Code: {e.code}")
        logger.error(f"Detail: {e.detail}")
        raise
        
    except VerifactuSOAPTransportError as e:
        batch.response = "Error, no response received"
        batch.response_status = "Error"
        batch.save(update_fields=['response', 'response_status'])
        logger.error("=" * 80)
        logger.error("TRANSPORT ERROR")
        logger.error("=" * 80)
        logger.error(f"Message: {e.message}")
        logger.error(f"Status Code: {e.status_code}")
        logger.error("\nThis might be due to:")
        logger.error("  - Network connectivity issues")
        logger.error("  - SSL certificate problems")
        logger.error("  - Incorrect WSDL URL")
        logger.error("  - Missing or incorrect client certificates")
        raise
        
    except Exception as e:
        batch.response = "Error, no response received"
        batch.response_status = "Error"
        batch.save(update_fields=['response', 'response_status'])
        logger.error("=" * 80)
        logger.error("UNEXPECTED ERROR")
        logger.error("=" * 80)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        logger.error("Traceback:")
        logger.error(traceback.format_exc())
        raise