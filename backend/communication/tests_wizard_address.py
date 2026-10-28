from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from billing.models import Invoice
from communication.models import CommunicationProcess, CommunicationStatus, MessageType
from communication.tasks import get_communication_process_data
from communication.utils.message_service import create_comm_from_persons
from contract.models import Contract
from coredata.models import Address, ConfigProject, Person, PersonAddress
from service.models import Company, CompanyConfig


class WizardAddressModeTests(SimpleTestCase):
    def test_filter_results_keep_the_effective_address_mode_for_save(self):
        cases = (
            ('CONTRACT', {}, 'default', 'filter_by_contract'),
            ('CONTRACT', {'address_type': 'contract'}, 'contract', 'filter_by_contract'),
            ('BILLING', {'address_type': 'invoice'}, 'invoice', 'filter_by_billing'),
            ('SUPPLYPOINT', {}, 'contract', 'filter_by_supply_point'),
            ('SUPPLYCUT', {}, 'contract', 'filter_by_supply_cut'),
            ('SUPPLYCUT', {'address_type': 'default'}, 'default', 'filter_by_supply_cut'),
            ('FIXED', {'entity': 'billing'}, 'invoice', 'filter_by_fixed_billing'),
            ('FIXED', {'entity': 'claimrequest'}, 'contract', 'filter_by_claim_request'),
            ('FIXED', {'entity': 'supplycut', 'address_type': 'default'}, 'default', 'filter_by_supply_cut'),
        )
        for filter_type, filters, expected, filter_name in cases:
            with self.subTest(filter_type=filter_type, filters=filters), patch(
                f'communication.views.manage_communication_process_view.{filter_name}',
                return_value=[{'id': 1}],
            ):
                result = get_communication_process_data.run({'type': filter_type, 'filters': filters})
                self.assertEqual(result['persons'][0]['address_type'], expected)


class WizardAddressCompanySplitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for token, value in (
            ('use_multiple_companies', 'true'),
            ('contract_terminated_status', 'terminated'),
            ('invoice_type_invoice_token', 'invoice'),
            ('message_type_email_token', 'email'),
            ('message_type_letter_token', 'letter'),
        ):
            ConfigProject.objects.create(token=token, value=value)
        CommunicationStatus.objects.create(token='pending', is_default=True)
        MessageType.objects.create(token='email', name='Email')
        MessageType.objects.create(token='letter', name='Letter')
        cls.company_config = CompanyConfig.objects.create()
        cls.person = Person.objects.create(name='Wizard recipient')
        cls.default_address = Address.objects.create(address_extra='Person address')
        PersonAddress.objects.create(person=cls.person, address=cls.default_address)
        cls.contract_address = Address.objects.create(address_extra='Contract address')
        contact_address = PersonAddress.objects.create(person=cls.person, address=cls.contract_address)
        cls.first_contract = Contract.objects.create(
            holder=cls.person, company=Company.objects.create(name='First company'),
            communication_type='PAPER', address_contact=contact_address,
        )
        cls.second_contract = Contract.objects.create(
            holder=cls.person, company=Company.objects.create(name='Second company'),
            communication_type='PAPER',
        )
        cls.invoices = Invoice.objects.bulk_create([
            Invoice(contract=cls.first_contract, address_final='Invoice snapshot address'),
            Invoice(contract=cls.second_contract, address_final='Other invoice address'),
        ])

    def create_communications(self, address_type=None, contracts=None, invoices=None):
        process = CommunicationProcess.objects.create(type_tokens='default')
        person = {
            'id': self.person.id,
            'contracts': contracts if contracts is not None else [self.first_contract.id, self.second_contract.id],
            'invoices': invoices or [],
        }
        if address_type is not None:
            person['address_type'] = address_type
        with patch('communication.utils.message_service.get_communication_file', return_value=None):
            self.assertTrue(create_comm_from_persons(
                None, [person], process, self.company_config, 'Default', 'default', None, False,
            ))
        return list(process.communications.order_by('id'))

    def assert_split(self, communications, expected_address):
        self.assertEqual(len(communications), 2)
        self.assertEqual(
            {tuple(comm.contracts.values_list('id', flat=True)) for comm in communications},
            {(self.first_contract.id,), (self.second_contract.id,)},
        )
        for comm in communications:
            self.assertEqual(comm.used_address, expected_address)
            self.assertEqual(comm.type_tokens, 'letter')
            self.assertEqual(comm.preferred_communication_type, 'PAPER')

    def test_person_address_survives_company_split_without_linked_contract_address(self):
        self.assert_split(self.create_communications('default'), str(self.default_address))

    def test_contract_address_survives_company_split_without_linked_contract_address(self):
        self.assert_split(self.create_communications('contract'), str(self.contract_address))

    def test_legacy_payload_preserves_original_group_address(self):
        self.assert_split(self.create_communications(), str(self.contract_address))

    def test_invoice_snapshot_survives_company_split_inferred_from_invoices(self):
        self.assert_split(
            self.create_communications('invoice', contracts=[], invoices=[i.id for i in self.invoices]),
            'Invoice snapshot address',
        )

    def test_null_company_remains_a_separate_group(self):
        Contract.objects.filter(id=self.second_contract.id).update(company=None)
        self.assert_split(self.create_communications('default'), str(self.default_address))

    def test_single_company_mode_keeps_contracts_together(self):
        ConfigProject.objects.filter(token='use_multiple_companies').update(value='false')
        communications = self.create_communications('default')
        self.assertEqual(len(communications), 1)
        self.assertEqual(communications[0].contracts.count(), 2)
        self.assertEqual(communications[0].used_address, str(self.default_address))

    def test_communication_type_still_splits_contracts_of_the_same_company(self):
        Contract.objects.filter(id=self.second_contract.id).update(
            company=self.first_contract.company, communication_type='DIGITAL',
        )
        communications = self.create_communications('default')
        self.assertEqual(len(communications), 2)
        self.assertEqual({c.preferred_communication_type for c in communications}, {'PAPER', 'DIGITAL'})
        self.assertTrue(all(c.used_address == str(self.default_address) for c in communications))

    def test_missing_selected_address_does_not_fall_back_to_a_different_mode(self):
        PersonAddress.objects.filter(person=self.person).update(is_active=False)
        communications = self.create_communications('default')
        self.assertEqual(len(communications), 2)
        self.assertTrue(all(c.used_address is None for c in communications))
