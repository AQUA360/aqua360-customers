from contextlib import ExitStack
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from communication.utils.communication_service import get_communication_logo
from service.utils.contract_company import company_colors, contract_company_logo


@override_settings(DOMAIN_MEDIA='https://media.example')
class CommunicationLogoTests(SimpleTestCase):
    """Amb `use_multiple_companies` el logo és el de l'empresa del contracte."""

    config_company = {'logo': 'https://media.example/media/uploads/logo/1/config.png'}

    def build_communication(self, contract_logo):
        contract = MagicMock()
        contract.company.logo.name = contract_logo
        contract.company.logo.__bool__.return_value = bool(contract_logo)
        communication = MagicMock()
        communication.contracts.select_related.return_value.first.return_value = contract
        return communication

    @patch('service.utils.contract_company.use_multiple_companies', return_value=True)
    @patch('communication.utils.communication_service.use_multiple_companies', return_value=True)
    def test_multiple_companies_uses_contract_company_logo(self, *_):
        communication = self.build_communication('uploads/logo/2/contract.png')
        self.assertEqual(
            get_communication_logo(communication, self.config_company),
            'https://media.example/media/uploads/logo/2/contract.png',
        )

    @patch('service.utils.contract_company.use_multiple_companies', return_value=True)
    @patch('communication.utils.communication_service.use_multiple_companies', return_value=True)
    def test_multiple_companies_contract_company_without_logo_falls_back(self, *_):
        communication = self.build_communication('')
        self.assertEqual(
            get_communication_logo(communication, self.config_company),
            'https://media.example/media/uploads/logo/1/config.png',
        )

    @patch('service.utils.contract_company.use_multiple_companies', return_value=False)
    @patch('communication.utils.communication_service.use_multiple_companies', return_value=False)
    def test_single_company_uses_config_company_logo(self, *_):
        communication = self.build_communication('uploads/logo/2/contract.png')
        self.assertEqual(
            get_communication_logo(communication, self.config_company),
            'https://media.example/media/uploads/logo/1/config.png',
        )

    @patch('service.utils.contract_company.use_multiple_companies', return_value=True)
    @patch('communication.utils.communication_service.use_multiple_companies', return_value=True)
    def test_without_communication_uses_config_company_logo(self, *_):
        self.assertEqual(
            get_communication_logo(None, self.config_company),
            'https://media.example/media/uploads/logo/1/config.png',
        )


@override_settings(DOMAIN_MEDIA='https://media.example')
class ContractCompanyLogoTests(SimpleTestCase):
    """Helper compartit amb els documents d'impagats (p. ex. el recordatori de pagament)."""

    def build_contract(self, logo_name):
        contract = MagicMock()
        contract.company.logo.name = logo_name
        contract.company.logo.__bool__.return_value = bool(logo_name)
        return contract

    @patch('service.utils.contract_company.use_multiple_companies', return_value=True)
    def test_multiple_companies_returns_contract_company_logo(self, _):
        self.assertEqual(
            contract_company_logo(self.build_contract('uploads/logo/2/contract.png')),
            'https://media.example/media/uploads/logo/2/contract.png',
        )

    @patch('service.utils.contract_company.use_multiple_companies', return_value=False)
    def test_single_company_returns_none(self, _):
        self.assertIsNone(contract_company_logo(self.build_contract('uploads/logo/2/contract.png')))

    @patch('service.utils.contract_company.use_multiple_companies', return_value=True)
    def test_contract_company_without_logo_returns_none(self, _):
        self.assertIsNone(contract_company_logo(self.build_contract('')))


class CompanyColorsTests(SimpleTestCase):
    """Els colors surten de la primera empresa que en té (la del contracte primer)."""

    def company(self, main=None, secondary=None):
        return MagicMock(invoice_main_color=main, invoice_secondary_color=secondary)

    @patch('service.utils.contract_company.ConfigProject')
    def test_first_company_with_colors_wins(self, _):
        self.assertEqual(
            company_colors(self.company('#111111', '#222222'), self.company('#333333', '#444444')),
            ('#111111', '#222222'),
        )

    @patch('service.utils.contract_company.ConfigProject')
    def test_falls_back_per_color_to_next_company(self, _):
        self.assertEqual(
            company_colors(self.company('#111111', None), self.company('#333333', '#444444')),
            ('#111111', '#444444'),
        )

    @patch('service.utils.contract_company.ConfigProject')
    def test_falls_back_to_config_project_then_default(self, config_project):
        config_project.objects.filter.return_value.first.side_effect = [MagicMock(value='#555555'), None]
        self.assertEqual(company_colors(None, self.company()), ('#555555', '#ffffff'))


class SingleCompanyUntouchedTests(SimpleTestCase):
    """Sense `use_multiple_companies` no es consulta ni el contracte ni la seva empresa."""

    @patch('communication.utils.communication_service.use_multiple_companies', return_value=False)
    def test_communication_logo_does_not_query_contracts(self, _):
        communication = MagicMock()
        get_communication_logo(communication, {'logo': None})
        communication.contracts.select_related.assert_not_called()


@override_settings(DOMAIN_MEDIA='https://media.example')
class CommunicationLetterCompanyTests(SimpleTestCase):
    def test_letter_rejects_contracts_from_different_companies_before_rendering(self):
        from communication.utils import communication_service as service

        for company_ids in ([1, 2], [1, None], [None, 1]):
            with self.subTest(company_ids=company_ids), ExitStack() as stack:
                communication = MagicMock()
                communication.contracts.values_list.return_value = company_ids
                stack.enter_context(patch.object(service, 'use_multiple_companies', return_value=True))
                stack.enter_context(patch.object(service, 'ConfigProject'))
                files = stack.enter_context(patch.object(service, 'CommunicationFile'))
                files.objects.get.return_value.communication = communication
                values = stack.enter_context(patch.object(service, 'get_com_values'))
                render = stack.enter_context(patch.object(service, 'render_to_string'))
                pdf = stack.enter_context(patch.object(service, 'pisa'))
                sign = stack.enter_context(patch.object(service, 'sign_pdf'))
                upload = stack.enter_context(patch.object(service, 'upload_document'))

                with self.assertRaisesMessage(ValueError, 'contracts from different companies'):
                    service.get_communication_file(1)

                values.assert_not_called()
                render.assert_not_called()
                pdf.CreatePDF.assert_not_called()
                sign.assert_not_called()
                upload.assert_not_called()

    def test_letter_identity_and_branding_follow_contract_company_with_fallbacks(self):
        from communication.utils import communication_service as service

        for multiple, company_ids, has_logo in (
            (True, [1], True), (True, [1, 1], True), (True, [1], False),
            (True, [None], False), (True, [None, None], False),
            (True, [], False), (False, [1], True), (False, [1, 2], True),
        ):
            with self.subTest(multiple=multiple, company_ids=company_ids, has_logo=has_logo), ExitStack() as stack:
                config_data = {
                    'name': 'Configured company', 'phone': '111',
                    'contact_email': 'config@example.test', 'address_complete': 'Config street',
                    'logo': 'uploads/logo/config.png',
                }
                contract_data = {
                    'name': 'Contract company', 'phone': '222',
                    'contact_email': 'contract@example.test', 'address_complete': 'Contract street',
                    'logo': 'uploads/logo/contract.png' if has_logo else None,
                }
                config_company = MagicMock(invoice_main_color='#111111', invoice_secondary_color='#222222')
                contract_company = MagicMock(invoice_main_color='#333333', invoice_secondary_color='#444444')
                contract_company.logo = MagicMock(name=contract_data['logo']) if has_logo else None
                if has_logo:
                    contract_company.logo.name = contract_data['logo']
                contracts = []
                for index, company_id in enumerate(company_ids, start=1):
                    contract = MagicMock(
                        company=contract_company if company_id else None,
                        company_id=company_id, token=f'C{index}', total_persons=index,
                    )
                    contract.consumption_stats.exists.return_value = False
                    contract.supply_point_default.connection = None
                    contracts.append(contract)
                contract = contracts[0] if contracts else None
                communication = MagicMock(person=None, due_date=None, company_config_email=None, process_id=None)
                communication.company_config.company_configs.all.return_value = MagicMock(
                    **{'__len__.return_value': 1, 'first.return_value': config_company})
                communication.contracts.first.return_value = contract
                communication.contracts.select_related.return_value.first.return_value = contract
                communication.contracts.all.return_value = contracts
                communication.contracts.values_list.return_value = company_ids
                for relation in (communication.invoices, communication.readings):
                    relation.first.return_value = None
                    relation.all.return_value = []
                message = communication.messages.get.return_value
                message.subject = '%company.name'
                message.body = '%company.phone %company.email %company.address_complete %contract.token %contract.persons'

                def mock(name, **kwargs):
                    return stack.enter_context(patch.object(service, name, **kwargs))

                stack.enter_context(patch('service.utils.contract_company.use_multiple_companies', return_value=multiple))
                mock('use_multiple_companies', return_value=multiple)
                mock('ConfigProject')
                files = mock('CommunicationFile')
                files.objects.get.return_value.communication = communication
                mock('CompanySerializer', side_effect=lambda company: MagicMock(
                    data=contract_data if company is contract_company else config_data))
                render = mock('render_to_string', return_value='<html></html>')
                mock('pisa').CreatePDF.return_value.err = False
                sign = mock('sign_pdf', return_value=BytesIO(b'pdf'))
                mock('upload_document')

                service.get_communication_file(1)

                uses_contract = multiple and bool(company_ids) and company_ids[0] is not None
                expected = contract_data if uses_contract else config_data
                context = render.call_args.args[1]
                self.assertEqual(render.call_args.args[0], 'basic_letter.html')
                self.assertEqual(context['company'], expected)
                self.assertEqual(context['subject'], expected['name'])
                for key in ('phone', 'contact_email', 'address_complete'):
                    self.assertIn(expected[key], context['body'])
                if contracts:
                    self.assertIn('<br>'.join(contract.token for contract in contracts), context['body'])
                    total_persons = sum(contract.total_persons for contract in contracts)
                    self.assertTrue(context['body'].endswith(f'{total_persons}</p>'))
                if not multiple:
                    communication.contracts.values_list.assert_not_called()
                self.assertEqual(context['main_color'], '#333333' if uses_contract else '#111111')
                self.assertEqual(context['secondary_color'], '#444444' if uses_contract else '#222222')
                logo = contract_data['logo'] if uses_contract and has_logo else config_data['logo']
                self.assertEqual(context['logo'], f'https://media.example/media/{logo}')
                self.assertEqual(sign.call_args.args[1], expected)
