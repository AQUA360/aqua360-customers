from unittest.mock import patch

from communication.models import CommunicationProcess
from communication.serializers.communication_process_serializer import CommunicationProcessSaveSerializer
from communication.tests import SupplyCutProcessTestCase
from service.models import Company


class CommunicationProcessAttachmentsTests(SupplyCutProcessTestCase):
    """La tria de documents adjunts de l'assistent queda desada al procés."""

    def save_process(self, **payload):
        serializer = CommunicationProcessSaveSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        with patch(
            'communication.serializers.communication_process_serializer.process_communication_creation_task'
        ):
            with self.captureOnCommitCallbacks(execute=True):
                process = serializer.save()
        return CommunicationProcess.objects.get(id=process.id)

    def test_choice_is_saved(self):
        process = self.save_process(
            attach_letter=True, attach_invoices=True, attach_readings=True,
            attach_reading_invoices=True, invoice_email_delivery='attachment',
        )
        self.assertTrue(process.attach_letter)
        self.assertTrue(process.attach_invoices)
        self.assertTrue(process.attach_readings)
        self.assertTrue(process.attach_reading_invoices)
        self.assertEqual(process.invoice_email_delivery, Company.INVOICE_EMAIL_ATTACHMENT)
        # Fora de la gestió d'impagats no hi ha document del pas
        self.assertIsNone(process.attach_claim_documents)

    def test_without_invoices_readings_and_delivery_are_not_saved(self):
        process = self.save_process(attach_readings=True, invoice_email_delivery='ov_link')
        self.assertFalse(process.attach_letter)
        self.assertFalse(process.attach_invoices)
        self.assertFalse(process.attach_readings)
        self.assertFalse(process.attach_reading_invoices)
        self.assertIsNone(process.invoice_email_delivery)

    def test_delivery_is_saved_with_reading_invoices(self):
        process = self.save_process(attach_reading_invoices=True, invoice_email_delivery='both')
        self.assertEqual(process.invoice_email_delivery, Company.INVOICE_EMAIL_BOTH)
