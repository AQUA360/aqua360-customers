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
