from unittest.mock import patch

from django.test import TestCase

from billing.models import Invoice
from communication.models import (
    Communication, CommunicationFile, CommunicationProcess, CommunicationStatus, MessageTemplate, MessageType,
)
from communication.serializers.communication_process_serializer import CommunicationProcessSaveSerializer
from communication.tests import SupplyCutProcessTestCase
from communication.utils.communication_service import get_com_values, invoices_attached_to_email
from communication.utils.message_service import create_comm_from_persons
from contract.models import Contract
from coredata.models import Address, ConfigProject, Person
from documentmanager.models import Document
from service.models import Company, CompanyConfig, SupplyPoint


class InvoiceEmailDeliveryTests(TestCase):
    """Factures adjuntes al correu o enllaç a l'oficina virtual, segons l'empresa o el procés."""

    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('use_multiple_companies', 'true'),
            ('contract_terminated_status', 'terminated'),
            ('invoice_type_invoice_token', 'invoice'),
            ('message_type_email_token', 'email'),
            ('message_type_letter_token', 'letter'),
        ):
            ConfigProject.objects.update_or_create(token=token, defaults={'value': value})
        CommunicationStatus.objects.create(token='pending', is_default=True)
        MessageType.objects.create(token='email', name='Email')
        MessageType.objects.create(token='letter', name='Letter')
        cls.company_config = CompanyConfig.objects.create()
        cls.person = Person.objects.create(name='Recipient')
        cls.ov_company = Company.objects.create(
            name='OV company', virtual_office_url='https://ov.example.com',
            invoice_email_delivery=Company.INVOICE_EMAIL_OV_LINK,
        )
        cls.attachment_company = Company.objects.create(name='Attachment company')
        # Les variables del missatge necessiten el punt de subministrament del contracte
        supply_point = SupplyPoint.objects.create(token='SP-1', address=Address.objects.create())
        cls.ov_contract = Contract.objects.create(
            token='C1', supply_point_default=supply_point, holder=cls.person, company=cls.ov_company, communication_type='PAPER',
        )
        cls.attachment_contract = Contract.objects.create(
            token='C2', supply_point_default=supply_point, holder=cls.person, company=cls.attachment_company, communication_type='PAPER',
        )
        # bulk_create: el `save()` de la factura dispara senyals que necessiten més configuració
        cls.invoices = Invoice.objects.bulk_create([
            Invoice(
                contract=contract,
                invoice_file=Document.objects.create(entity_id=0, service='hdd', document_name='invoice.pdf'),
            )
            for contract in (cls.ov_contract, cls.attachment_contract)
        ])

    def create_communications(self, invoice_email_delivery=None):
        process = CommunicationProcess.objects.create(type_tokens='default')
        person = {'id': self.person.id, 'contracts': [], 'invoices': [invoice.id for invoice in self.invoices]}
        with patch('communication.utils.message_service.get_communication_file', return_value=None):
            self.assertTrue(create_comm_from_persons(
                None, [person], process, self.company_config, 'Default', 'default', None, False,
                attach_invoices=True, invoice_email_delivery=invoice_email_delivery,
            ))
        return process

    def attach_to_email_by_company(self, process):
        return {
            comm_file.communication.contracts.get().company_id: comm_file.attach_to_email
            for comm_file in CommunicationFile.objects.filter(communication__process=process, file__isnull=False)
        }

    def test_company_setting_decides_whether_the_invoice_is_attached(self):
        process = self.create_communications()
        self.assertEqual(
            self.attach_to_email_by_company(process),
            {self.ov_company.id: False, self.attachment_company.id: True},
        )
        # El PDF continua vinculat a la comunicació (arxiu i carta)
        self.assertEqual(
            CommunicationFile.objects.filter(communication__process=process, attach_to_letter=True).count(), 2,
        )

    def test_process_choice_overrides_the_company_setting(self):
        process = self.create_communications(Company.INVOICE_EMAIL_ATTACHMENT)
        self.assertEqual(set(self.attach_to_email_by_company(process).values()), {True})

        process = self.create_communications(Company.INVOICE_EMAIL_OV_LINK)
        self.assertEqual(set(self.attach_to_email_by_company(process).values()), {False})

    def test_both_keeps_the_attachment(self):
        Company.objects.filter(id=self.ov_company.id).update(invoice_email_delivery=Company.INVOICE_EMAIL_BOTH)
        process = self.create_communications()
        self.assertEqual(set(self.attach_to_email_by_company(process).values()), {True})

    def test_single_company_uses_the_sending_configuration_company(self):
        ConfigProject.objects.filter(token='use_multiple_companies').update(value='false')
        Company.objects.filter(id=self.attachment_company.id).update(config=self.company_config)
        comm = Communication.objects.create(company_config=self.company_config)
        comm.contracts.set([self.ov_contract])
        self.assertTrue(invoices_attached_to_email(comm))

        Company.objects.filter(id=self.attachment_company.id).update(
            invoice_email_delivery=Company.INVOICE_EMAIL_OV_LINK,
        )
        self.assertFalse(invoices_attached_to_email(comm))

    def test_ov_url_message_variable(self):
        comm = Communication.objects.create(company_config=self.company_config)
        comm.contracts.set([self.ov_contract])
        self.assertEqual(get_com_values(None, comm, None)['company.ov_url'], 'https://ov.example.com')

        comm.contracts.set([self.attachment_contract])
        self.assertEqual(get_com_values(None, comm, None)['company.ov_url'], '')

    def test_email_body_renders_the_ov_url_as_a_link(self):
        from communication.models import Message
        from communication.utils.communication_service import create_email_template
        Company.objects.filter(id=self.attachment_company.id).update(config=self.company_config)
        comm = Communication.objects.create(company_config=self.company_config)
        comm.contracts.set([self.ov_contract])
        comm.messages.set([Message.objects.create(
            type=MessageType.objects.get(token='email'), subject='Factura', body='Consulta-la a %company.ov_url',
        )])
        with patch('communication.utils.communication_service.render_to_string', return_value='') as render:
            create_email_template(comm)
        self.assertIn(
            '<a href="https://ov.example.com">https://ov.example.com</a>', render.call_args.args[1]['body'],
        )


class InvoiceEmailDeliveryProcessTests(SupplyCutProcessTestCase):
    """El valor del procés mana; si no n'hi ha, el de la plantilla; si tampoc, el de l'empresa (None)."""

    def saved_delivery(self, **payload):
        serializer = CommunicationProcessSaveSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        with patch(
            'communication.serializers.communication_process_serializer.process_communication_creation_task'
        ) as task:
            with self.captureOnCommitCallbacks(execute=True):
                serializer.save()
        return task.delay.call_args.kwargs['invoice_email_delivery']

    def test_template_value_is_used_when_process_does_not_send_it(self):
        template = MessageTemplate.objects.create(name='Factures', invoice_email_delivery=Company.INVOICE_EMAIL_OV_LINK)
        self.assertEqual(self.saved_delivery(message_template_id=str(template.id)), Company.INVOICE_EMAIL_OV_LINK)

    def test_process_value_overrides_the_template(self):
        template = MessageTemplate.objects.create(name='Factures', invoice_email_delivery=Company.INVOICE_EMAIL_OV_LINK)
        self.assertEqual(
            self.saved_delivery(message_template_id=str(template.id), invoice_email_delivery='attachment'),
            Company.INVOICE_EMAIL_ATTACHMENT,
        )

    def test_without_process_or_template_value_the_company_decides(self):
        template = MessageTemplate.objects.create(name='Factures')
        self.assertIsNone(self.saved_delivery(message_template_id=str(template.id)))
