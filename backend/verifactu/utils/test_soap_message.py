"""
Test script for sending example SOAP XML message to Verifactu service.

This script sends the example "alta inicial" (initial registration) message
as specified in the Verifactu documentation.
"""

import logging
from verifactu.utils.soap_client_service import VerifactuSOAPClient, VerifactuSOAPFault, VerifactuSOAPTransportError
from django.conf import settings
from decouple import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_example_invoice_data():
    """
    Build the example invoice data structure matching the XML schema.
    
    The operation expects Cabecera and RegistroFactura directly as parameters,
    not nested under RegFactuSistemaFacturacion.
    
    Returns:
        Dictionary with the invoice data structure
        
    Verify (qr url) pre:
        https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?nif=XXXXXXXXY&numserie=YYYY...YYYY&fecha=DD-MM-AAAA&importe=NNNNNNNNN.DD
        Example:
            https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?nif=00000000T&numserie=123456&fecha=13-09-2024&importe=0.00
    Verify prod: https://www2.agenciatributaria.gob.es
    """
    return {
        'Cabecera': {
            'ObligadoEmision': {
                'NombreRazon': 'Emisor de proves',
                'NIF': '00000000T'
            }
        },
        'RegistroFactura': [  # Note: This is a list as per the signature
            {
                'RegistroAlta': {
                    'IDVersion': '1.0',
                    'IDFactura': {
                        'IDEmisorFactura': '00000000T',
                        'NumSerieFactura': '12345678',
                        'FechaExpedicionFactura': '13-09-2024'
                    },
                    'NombreRazonEmisor': 'Emisor de proves',
                    'TipoFactura': 'F1',
                    'DescripcionOperacion': 'Descripc',
                    'Destinatarios': {
                        'IDDestinatario': {
                            'NombreRazon': 'Destinatari de proves',
                            'NIF': '00000001R'
                        }
                    },
                    'Desglose': {
                        'DetalleDesglose': [
                            {
                                'ClaveRegimen': '01',
                                'CalificacionOperacion': 'S1',
                                'TipoImpositivo': '0',
                                'BaseImponibleOimporteNoSujeto': '0',
                                'CuotaRepercutida': '0'
                            },
                            {
                                'ClaveRegimen': '01',
                                'CalificacionOperacion': 'S1',
                                'TipoImpositivo': '0',
                                'BaseImponibleOimporteNoSujeto': '0',
                                'CuotaRepercutida': '0'
                            }
                        ]
                    },
                    'CuotaTotal': '0',
                    'ImporteTotal': '0',
                    'Encadenamiento': {
                        'RegistroAnterior': {
                            'IDEmisorFactura': '00000000T',
                            'NumSerieFactura': '44',
                            'FechaExpedicionFactura': '13-09-2024',
                            'Huella': 'HuellaRegistroAnterior'
                        }
                    },
                    'SistemaInformatico': dict(settings.VERIFACTU_SISTEMA_INFORMATICO),
                    'FechaHoraHusoGenRegistro': '2024-09-13T19:20:30+01:00',
                    'TipoHuella': '01',
                    'Huella': 'Huella'
                }
            }
        ]
    }
    
def build_example_invoice_data_canceled():
    """
    Cancel previous invoice
    
    """
    return {
        'Cabecera': {
            'ObligadoEmision': {
                'NombreRazon': 'Emisor de proves',
                'NIF': '00000000T'
            }
        },
        'RegistroFactura': [  # Note: This is a list as per the signature
            {
                'RegistroAnulacion': {
                    'IDVersion': '1.0',
                    'IDFactura': {
                        'IDEmisorFacturaAnulada': '00000000T',
                        'NumSerieFacturaAnulada': '12345',
                        'FechaExpedicionFacturaAnulada': '13-09-2024'
                    },
                    'Encadenamiento': {
                        'RegistroAnterior': {
                            'IDEmisorFactura': '00000000T',
                            'NumSerieFactura': '44',
                            'FechaExpedicionFactura': '13-09-2024',
                            'Huella': 'HuellaRegistroAnterior'
                        }
                    },
                    'SistemaInformatico': dict(settings.VERIFACTU_SISTEMA_INFORMATICO),
                    'FechaHoraHusoGenRegistro': '2024-09-13T19:20:30+01:00',
                    'TipoHuella': '01',
                    'Huella': 'Huella'
                }
            }
        ]
    }


def build_consultation_data(ejercicio=2024, periodo=9):
    periodo_str = f"{periodo:02d}"  # Format as 2-digit string with zero padding
    return {
        'Cabecera': {
            'IDVersion': '1.0',
            'ObligadoEmision': {
                'NombreRazon': 'Emisor de proves',
                'NIF': '00000000T'
            }
        },
        'FiltroConsulta': {
            'PeriodoImputacion': {
                'Ejercicio': str(ejercicio),
                'Periodo': periodo_str
            }
        }
    }

def test_send_soap_message(action='send'):
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
        logger.info("Testing Verifactu SOAP - Example "+action)
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
        if action == 'send':
            # Build the invoice data
            xml_data = build_example_invoice_data()
            operation_name = 'RegFactuSistemaFacturacion'
            logger.info("Invoice data structure built successfully")
        elif action == 'cancel':
            # Build the cancellation data
            xml_data = build_example_invoice_data_canceled()
            operation_name = 'RegFactuSistemaFacturacion'
            logger.info("Cancellation data structure built successfully")
        elif action == 'consult':
            # Build the consultation data
            xml_data = build_consultation_data()
            operation_name = 'ConsultaFactuSistemaFacturacion'
            logger.info("Consultation data structure built successfully")
        
        # Send the SOAP request        
        # Call the service
        response = client.call_service(
            operation_name=operation_name,
            **xml_data  # Unpack the invoice data as keyword arguments
        )
        
        # Try to get raw XML response
        raw_xml = client.get_raw_xml_response()
        
        logger.info(f"\033[93mSOAP request completed\033[0m")

        return response
        
    except VerifactuSOAPFault as e:
        logger.error("=" * 80)
        logger.error("SOAP FAULT RECEIVED")
        logger.error("=" * 80)
        logger.error(f"Message: {e.message}")
        logger.error(f"Code: {e.code}")
        logger.error(f"Detail: {e.detail}")
        raise
        
    except VerifactuSOAPTransportError as e:
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
        logger.error("=" * 80)
        logger.error("UNEXPECTED ERROR")
        logger.error("=" * 80)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        import traceback
        logger.error("Traceback:")
        logger.error(traceback.format_exc())
        raise
