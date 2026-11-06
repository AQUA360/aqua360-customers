from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from contract.utils import contract_termination_service


class _StopRender(Exception):
    pass


class TerminationDocumentContextTest(SimpleTestCase):
    """El document de baixa rep el logo de l'explotació sense tocar `exploitation_image`."""

    def _render_context(self, logo_source):
        instance = MagicMock()
        instance.readings.count.return_value = 1
        captured = {}

        def fake_render(template_name, context):
            captured.update(context)
            raise _StopRender()

        module = 'contract.utils.contract_termination_service'
        with patch(f'{module}.CompanySerializer') as company_serializer, \
                patch(f'{module}.PersonCardSerializer'), \
                patch(f'{module}.AddressSerializer'), \
                patch(f'{module}.ConfigProject'), \
                patch(f'{module}.exploitation_logo_source', return_value=logo_source) as logo_mock, \
                patch(f'{module}.render_to_string', side_effect=fake_render):
            company_serializer.return_value.data = {'logo': None}
            with self.assertRaises(_StopRender):
                contract_termination_service.getTerminationDocument(instance)

        logo_mock.assert_called_once_with(instance.contract.supply_point_default.connection.exploitation)
        return captured

    def test_passes_exploitation_logo(self):
        context = self._render_context('/media/uploads/exploitation/1/logo.png')
        self.assertEqual(context['exploitation_logo'], '/media/uploads/exploitation/1/logo.png')

    def test_does_not_pass_exploitation_image(self):
        # Hi ha plantilles personalitzades que ja fan servir `exploitation_image`
        # i no han de canviar.
        context = self._render_context('/media/uploads/exploitation/1/logo.png')
        self.assertNotIn('exploitation_image', context)

    def test_without_exploitation_logo(self):
        context = self._render_context(None)
        self.assertIsNone(context['exploitation_logo'])
