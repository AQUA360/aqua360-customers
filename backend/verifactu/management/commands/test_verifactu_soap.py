"""
Django management command to test Verifactu SOAP message sending.

Usage:
    python manage.py test_verifactu_soap
    python manage.py test_verifactu_soap --xml-only  # Just generate XML, don't send
"""

from django.core.management.base import BaseCommand
from verifactu.utils.test_soap_message import (
    test_send_soap_message
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test sending example SOAP XML message to Verifactu service'

    def add_arguments(self, parser):
        parser.add_argument(
            '--consult',
            action='store_true',
            help='Query previously submitted invoices instead of sending new invoice',
        )
        parser.add_argument(
            '--cancel',
            action='store_true',
            help='Cancel previously submitted invoice instead of sending new invoice',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        if options['verbose']:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('Verifactu SOAP Test'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        
        
        try:
            if options['consult']:
                self.stdout.write('Sending consultation SOAP request to Verifactu service...')
                self.stdout.write('')
                response = test_send_soap_message(action='consult')
                    
            elif options['cancel']:
                self.stdout.write('Sending cancellation SOAP request to Verifactu service...')
                self.stdout.write('')
                response = test_send_soap_message(action='cancel')
            else:
                self.stdout.write('Sending SOAP request to Verifactu service...')
                self.stdout.write('')
                response = test_send_soap_message()
                
            if response:
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('=' * 80))
                self.stdout.write(self.style.SUCCESS('Test completed successfully!'))
                self.stdout.write(self.style.SUCCESS('=' * 80))
                self.stdout.write('')
                self.stdout.write('Response received:')
                self.stdout.write(str(response))
                
                responseStatus = response.get('EstadoEnvio')
                
                if responseStatus == 'Correcto':
                    self.stdout.write(self.style.SUCCESS('SOAP request completed successfully!'))
                elif responseStatus == 'ParcialmenteCorrecto':
                    self.stdout.write(self.style.WARNING('SOAP request completed partially successfully!'))
                elif responseStatus == 'Incorrecto':
                    self.stdout.write(self.style.ERROR('SOAP request completed with errors!'))
                
            else:
                self.stdout.write('')
                self.stdout.write(self.style.WARNING('Test completed but no response received'))

        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('=' * 80))
            self.stdout.write(self.style.ERROR('Consultation failed with error'))
            self.stdout.write(self.style.ERROR('=' * 80))
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Make sure you have configured:'))
            self.stdout.write('  - VERIFACTU_WSDL_URL in your .env file')
            self.stdout.write('  - VERIFACTU_CERT_FILE_PATH (if required)')
            self.stdout.write('  - VERIFACTU_CERT_KEY (if required)')
            raise

