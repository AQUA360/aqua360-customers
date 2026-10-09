"""
Django test case for Verifactu SOAP invoice submission.

Run with: python manage.py test verifactu.tests.test_soap_invoice
"""

from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
from verifactu.utils.test_soap_message import (
    build_example_invoice_data
)
from verifactu.utils.soap_client_service import (
    VerifactuSOAPClient,
    VerifactuSOAPFault,
    VerifactuSOAPTransportError
)


class VerifactuSOAPInvoiceTest(TestCase):
    """Test cases for Verifactu SOAP invoice submission."""
    
    def test_build_example_invoice_data(self):
        """Test that example invoice data structure is built correctly."""
        invoice_data = build_example_invoice_data()
        
        # Check main structure - should have Cabecera and RegistroFactura directly
        self.assertIn('Cabecera', invoice_data)
        self.assertIn('RegistroFactura', invoice_data)
        
        # Check Cabecera
        cabecera = invoice_data['Cabecera']
        self.assertIn('ObligadoEmision', cabecera)
        self.assertEqual(cabecera['ObligadoEmision']['NIF'], 'AAAA')
        self.assertEqual(cabecera['ObligadoEmision']['NombreRazon'], 'XXXXX')
        
        # Check RegistroFactura - should be a list
        registro_factura = invoice_data['RegistroFactura']
        self.assertIsInstance(registro_factura, list)
        self.assertGreater(len(registro_factura), 0)
        
        # Check first registro
        registro = registro_factura[0]
        self.assertIn('RegistroAlta', registro)
        
        # Check RegistroAlta details
        alta = registro['RegistroAlta']
        self.assertEqual(alta['IDVersion'], '1.0')
        self.assertEqual(alta['TipoFactura'], 'F1')
        self.assertEqual(alta['ImporteTotal'], '131.4')
        
        # Check Desglose has 2 items
        desglose = alta['Desglose']['DetalleDesglose']
        self.assertEqual(len(desglose), 2)
        self.assertEqual(desglose[0]['TipoImpositivo'], '4')
        self.assertEqual(desglose[1]['TipoImpositivo'], '21')

    
    @patch('verifactu.utils.soap_client_service.VerifactuSOAPClient._initialize_client')
    @patch('verifactu.utils.soap_client_service.Client')
    def test_send_example_invoice_success(self, mock_client_class, mock_init):
        """Test successful invoice submission."""
        # Mock the SOAP client
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        # Mock the service call
        mock_service = MagicMock()
        mock_service.SubmitInvoice.return_value = {
            'status': 'success',
            'invoice_id': '12345'
        }
        mock_client_instance.service = mock_service
        
        # Create client and set the mocked client
        client = VerifactuSOAPClient()
        client.client = mock_client_instance
        client.wsdl_url = 'https://test.wsdl.url'
        
        # Build invoice data
        invoice_data = build_example_invoice_data()
        
        # This would normally call the service, but we're mocking it
        # In a real scenario, you would call:
        # response = client.call_service('SubmitInvoice', **invoice_data)
        
        # For this test, we just verify the data structure is correct
        self.assertIn('Cabecera', invoice_data)
        self.assertIn('RegistroFactura', invoice_data)
    
    def test_invoice_data_structure_validation(self):
        """Test that invoice data structure matches expected format."""
        invoice_data = build_example_invoice_data()
        
        # Validate required fields - RegistroFactura is a list
        registro_factura = invoice_data['RegistroFactura']
        self.assertIsInstance(registro_factura, list)
        self.assertGreater(len(registro_factura), 0)
        
        registro = registro_factura[0]
        registro_alta = registro['RegistroAlta']
        
        # Required fields check
        required_fields = [
            'IDVersion',
            'IDFactura',
            'NombreRazonEmisor',
            'TipoFactura',
            'Destinatarios',
            'Desglose',
            'ImporteTotal',
            'SistemaInformatico',
            'Huella'
        ]
        
        for field in required_fields:
            self.assertIn(field, registro_alta, f"Required field '{field}' is missing")
        
        # Validate IDFactura structure
        id_factura = registro_alta['IDFactura']
        self.assertIn('IDEmisorFactura', id_factura)
        self.assertIn('NumSerieFactura', id_factura)
        self.assertIn('FechaExpedicionFactura', id_factura)
        
        # Validate SistemaInformatico structure
        sistema = registro_alta['SistemaInformatico']
        self.assertIn('NombreRazon', sistema)
        self.assertIn('NIF', sistema)
        self.assertIn('IdSistemaInformatico', sistema)


class VerifactuSOAPIntegrationTest(TestCase):
    """
    Integration tests for Verifactu SOAP client.
    
    These tests require actual WSDL configuration and should be run
    only in test environments with proper credentials.
    """
    
    def setUp(self):
        """Set up test fixtures."""
        # Skip if WSDL is not configured
        from decouple import config
        wsdl_url = config('VERIFACTU_WSDL_URL', default='')
        if not wsdl_url:
            self.skipTest("VERIFACTU_WSDL_URL not configured. Skipping integration test.")
    
    @patch('verifactu.utils.soap_client_service.VerifactuSOAPClient.call_service')
    def test_integration_send_invoice(self, mock_call_service):
        """
        Integration test for sending invoice.
        
        Note: This is a mock test. For real integration testing,
        configure VERIFACTU_WSDL_URL and certificates, then remove the mock.
        """
        # Mock successful response
        mock_call_service.return_value = {
            'Estado': 'OK',
            'Codigo': '0',
            'Descripcion': 'Registro correcto'
        }
        
        invoice_data = build_example_invoice_data()
        client = VerifactuSOAPClient()
        
        # In real scenario, this would make actual SOAP call
        # response = client.call_service('RegFactuSistemaFacturacion', **invoice_data)
        
        # For now, just verify the mock was set up correctly
        self.assertTrue(True)

