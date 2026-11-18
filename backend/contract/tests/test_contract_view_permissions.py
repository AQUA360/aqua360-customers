"""Permisos de lectura de les vistes principals de contractació (#2652).

Abans, `DjangoModelPermissions` no exigia cap permís per GET (i algunes vistes
només demanaven estar autenticat): qualsevol usuari llegia contractes,
sol·licituds, fiances o la gestió de consums. Ara GET requereix `view_*` del
model i l'escriptura, add/change/delete.
"""
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.db.models.fields.files import FieldFile
from django.test import TestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from contract.models import Contract, ContractRequest
from contract.views.bail_return_view import BailReturnViewSet
from contract.views.bail_view import BailViewSet
from contract.views.close_contract_termination_request_view import CloseContractTerminationRequestViewSet
from contract.views.consumption_management_view import ConsumptionManagementViewSet
from contract.views.contract_create_view import ContractCreateView
from contract.views.contract_manage_massively_view import ContractManageMassivelyViewSet
from contract.views.contract_ov_billing_view import ContractOVBillingView
from contract.views.contract_ov_view import ContractOVView
from contract.views.contract_pdf_view import ReportPDFDownloadViewSet
from contract.views.contract_request_finalize_view import FinalizeContractRequestView
from contract.views.contract_request_view import ContractRequestCreateContractView, ContractRequestViewSet
from contract.views.contract_view import ContractViewSet


def _perm(label):
    app_label, codename = label.split('.')
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def _user(username, *perms):
    user = User.objects.create_user(username, f'{username}@example.com', 'x')
    if perms:
        user.user_permissions.add(*[_perm(p) for p in perms])
    return user


class ContractViewPermissionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.no_perms = _user('no-perms-2652')
        cls.contract_viewer = _user('contract-viewer-2652', 'contract.view_contract')
        cls.request_viewer = _user('request-viewer-2652', 'contract.view_contractrequest')
        cls.bail_viewer = _user('bail-viewer-2652', 'contract.view_bail')
        cls.termination_viewer = _user('termination-viewer-2652', 'contract.view_contractterminationrequest')
        cls.factory = APIRequestFactory()

    def _call(self, view, method, path, user, data=None, **kwargs):
        request = getattr(self.factory, method)(path, data or {}, format='json')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return view(request, **kwargs)

    def _assert_read_and_write(self, view_list, view_create, path, viewer):
        self.assertEqual(self._call(view_list, 'get', path, self.no_perms).status_code, 403)
        self.assertEqual(self._call(view_list, 'get', path, viewer).status_code, 200)
        self.assertEqual(self._call(view_create, 'post', path, self.no_perms).status_code, 403)
        self.assertEqual(self._call(view_create, 'post', path, viewer).status_code, 403)

    def test_contract_viewset(self):
        # El queryset del llistat depèn de ConfigProject; aquí només interessa el permís.
        with patch.object(ContractViewSet, 'get_queryset', return_value=Contract.objects.none()):
            self._assert_read_and_write(
                ContractViewSet.as_view({'get': 'list'}),
                ContractViewSet.as_view({'post': 'create'}),
                '/contract/contract/', self.contract_viewer,
            )

    def test_contract_viewset_options_for_authenticated(self):
        view = ContractViewSet.as_view({'get': 'list'})
        self.assertEqual(self._call(view, 'options', '/contract/contract/', self.no_perms).status_code, 200)

    def test_contract_viewset_permissions_action_open(self):
        view = ContractViewSet.as_view({'get': 'permissions'})
        self.assertEqual(self._call(view, 'get', '/contract/contract/permissions/', self.no_perms).status_code, 200)

    def test_contract_request_viewset(self):
        self._assert_read_and_write(
            ContractRequestViewSet.as_view({'get': 'list'}),
            ContractRequestViewSet.as_view({'post': 'create'}),
            '/contract/contract-request/', self.request_viewer,
        )

    def test_bail_viewset(self):
        self._assert_read_and_write(
            BailViewSet.as_view({'get': 'list'}),
            BailViewSet.as_view({'post': 'create'}),
            '/contract/bail/', self.bail_viewer,
        )

    def test_consumption_management_requires_view_contract(self):
        view = ConsumptionManagementViewSet.as_view({'get': 'list'})
        self.assertEqual(self._call(view, 'get', '/contract/consumption-management/', self.no_perms).status_code, 403)
        self.assertEqual(self._call(view, 'get', '/contract/consumption-management/', self.request_viewer).status_code, 403)
        permissions_view = ConsumptionManagementViewSet.as_view({'get': 'permissions'})
        self.assertEqual(
            self._call(permissions_view, 'get', '/contract/consumption-management/permissions/', self.no_perms).status_code,
            200,
        )

    def test_consumption_management_list_with_view_contract(self):
        view = ConsumptionManagementViewSet.as_view({'get': 'list'})
        with patch('contract.views.consumption_management_view._get_fire_usage_token', return_value=[]), \
             patch('contract.views.consumption_management_view._get_fire_hydrant_items', return_value=[]), \
             patch('contract.views.consumption_management_view._get_inactive_consumption_items', return_value=[]), \
             patch('contract.views.consumption_management_view._get_duplicate_readings_items', return_value=[]):
            response = self._call(view, 'get', '/contract/consumption-management/', self.contract_viewer)
        self.assertEqual(response.status_code, 200)

    def test_contract_pdf_requires_view_of_downloaded_record(self):
        view = ReportPDFDownloadViewSet.as_view()
        path = '/contract/download/1/'
        self.assertEqual(self._call(view, 'get', path, self.no_perms, id=1).status_code, 403)
        # Sol·licitud: cal view_contractrequest; contracte: view_contract.
        self.assertEqual(self._call(view, 'get', path, self.contract_viewer, id=1).status_code, 403)
        self.assertEqual(
            self._call(view, 'get', f'{path}?is_contract=true', self.request_viewer, id=1).status_code, 403,
        )

    def test_contract_ov_view_requires_view_contract(self):
        view = ContractOVView.as_view()
        path = '/contract/contract-ov/X/'
        self.assertEqual(self._call(view, 'get', path, self.no_perms, contract_token='X').status_code, 403)
        self.assertEqual(self._call(view, 'get', path, self.request_viewer, contract_token='X').status_code, 403)

    def test_write_only_views_reject_viewers(self):
        cases = (
            (FinalizeContractRequestView.as_view(), 'put', '/contract/contract-request/finalize/1/',
             self.request_viewer, {'contract_request_id': 1}),
            (ContractRequestCreateContractView.as_view(), 'put', '/contract/contract-request/contract-create/1',
             self.request_viewer, {'id': 1}),
            (BailReturnViewSet.as_view(), 'put', '/contract/bail/return/1/', self.bail_viewer, {'id': 1}),
            (CloseContractTerminationRequestViewSet.as_view(), 'put', '/contract/contract-termination-request/close/1',
             self.termination_viewer, {'id': 1}),
            (ContractManageMassivelyViewSet.as_view(), 'post', '/contract/contract-manage/',
             self.contract_viewer, {}),
        )
        for view, method, path, viewer, kwargs in cases:
            with self.subTest(path=path):
                self.assertEqual(self._call(view, method, path, self.no_perms, **kwargs).status_code, 403)
                self.assertEqual(self._call(view, method, path, viewer, **kwargs).status_code, 403)


class RelatedModuleReadTestCase(TestCase):
    """Qui llegeix un mòdul relacionat (factures, ordres...) pot consultar
    contractes i sol·licituds, però no modificar-los; un mòdul no relacionat no."""

    @classmethod
    def setUpTestData(cls):
        cls.invoice_viewer = _user('invoice-viewer-2652', 'billing.view_invoice')
        cls.order_viewer = _user('order-viewer-2652', 'order.view_order')
        cls.pricing_viewer = _user('pricing-viewer-2652', 'pricing.view_pricerate')
        cls.factory = APIRequestFactory()

    def _call(self, view, method, path, user, data=None, **kwargs):
        request = getattr(self.factory, method)(path, data or {}, format='json')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return view(request, **kwargs)

    def test_contract_read_from_related_module(self):
        list_view = ContractViewSet.as_view({'get': 'list'})
        create_view = ContractViewSet.as_view({'post': 'create'})
        with patch.object(ContractViewSet, 'get_queryset', return_value=Contract.objects.none()):
            for user in (self.invoice_viewer, self.order_viewer):
                with self.subTest(user=user.username):
                    self.assertEqual(self._call(list_view, 'get', '/contract/contract/', user).status_code, 200)
                    self.assertEqual(self._call(create_view, 'post', '/contract/contract/', user).status_code, 403)
            self.assertEqual(
                self._call(list_view, 'get', '/contract/contract/', self.pricing_viewer).status_code, 403,
            )

    def test_contract_request_read_from_related_module(self):
        list_view = ContractRequestViewSet.as_view({'get': 'list'})
        create_view = ContractRequestViewSet.as_view({'post': 'create'})
        path = '/contract/contract-request/'
        self.assertEqual(self._call(list_view, 'get', path, self.invoice_viewer).status_code, 200)
        self.assertEqual(self._call(create_view, 'post', path, self.invoice_viewer).status_code, 403)
        self.assertEqual(self._call(list_view, 'get', path, self.pricing_viewer).status_code, 403)


class WriteActionsOnPostTestCase(TestCase):
    """Accions per POST que modifiquen registres existents (o que només
    consulten): s'exigeix el permís de l'operació real, no `add_*`."""

    @classmethod
    def setUpTestData(cls):
        cls.bail_adder = _user('bail-adder-2646', 'contract.add_bail')
        cls.bail_changer = _user('bail-changer-2646', 'contract.change_bail')
        cls.contract_adder = _user('contract-adder-2646', 'contract.add_contract')
        cls.contract_changer = _user('contract-changer-2646', 'contract.change_contract')
        cls.contract_viewer = _user('contract-viewer-2646', 'contract.view_contract')
        cls.invoice_viewer = _user('invoice-viewer-2646', 'billing.view_invoice')
        cls.request_changer = _user('request-changer-2646', 'contract.change_contractrequest')
        cls.request_and_contract_creator = _user(
            'request-contract-creator-2646', 'contract.change_contractrequest', 'contract.add_contract',
        )
        cls.factory = APIRequestFactory()

    def _call(self, view, method, path, user, data=None, **kwargs):
        request = getattr(self.factory, method)(path, data or {}, format='json')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return view(request, **kwargs)

    def test_bail_actions_on_existing_bails_require_change_bail(self):
        for name, path in (
            ('cancel_bail', '/contract/bail/cancel/'),
            ('return_bail_immediately', '/contract/bail/return-immediately/'),
            ('liquidate_bail', '/contract/bail/liquidate/'),
        ):
            with self.subTest(action=name), patch.object(BailViewSet, name, return_value=Response({})):
                view = BailViewSet.as_view({'post': name})
                self.assertEqual(self._call(view, 'post', path, self.bail_adder).status_code, 403)
                self.assertEqual(self._call(view, 'post', path, self.bail_changer).status_code, 200)

    def test_bail_create_still_requires_add_bail(self):
        view = BailViewSet.as_view({'post': 'create'})
        self.assertEqual(self._call(view, 'post', '/contract/bail/', self.bail_changer).status_code, 403)

    def test_contract_post_modifications_require_change_contract(self):
        cases = (
            (ContractManageMassivelyViewSet, 'post', '/contract/contract-manage/', {}),
            (ContractOVBillingView, 'post', '/contract/contract-ov/billing/X/', {'contract_token': 'X'}),
        )
        for view_cls, handler, path, kwargs in cases:
            with self.subTest(view=view_cls.__name__), patch.object(view_cls, handler, return_value=Response({})):
                view = view_cls.as_view()
                self.assertEqual(self._call(view, 'post', path, self.contract_adder, **kwargs).status_code, 403)
                self.assertEqual(self._call(view, 'post', path, self.contract_changer, **kwargs).status_code, 200)

    def test_contract_viewset_post_actions_require_change_contract(self):
        for name, path in (
            ('update_contract_bank_accounts', '/contract/contract/bank-change/'),
            ('save_documentation', '/contract/contract/1/save-documentation/'),
        ):
            with self.subTest(action=name), patch.object(ContractViewSet, name, return_value=Response({})):
                view = ContractViewSet.as_view({'post': name})
                self.assertEqual(self._call(view, 'post', path, self.contract_adder, pk=1).status_code, 403)
                self.assertEqual(self._call(view, 'post', path, self.contract_changer, pk=1).status_code, 200)

    def test_contract_ov_post_only_reads(self):
        path = '/contract/contract-ov/X/'
        with patch.object(ContractOVView, 'post', return_value=Response({})):
            view = ContractOVView.as_view()
            self.assertEqual(self._call(view, 'post', path, self.contract_adder, contract_token='X').status_code, 403)
            for user in (self.contract_viewer, self.invoice_viewer):
                with self.subTest(user=user.username):
                    self.assertEqual(self._call(view, 'post', path, user, contract_token='X').status_code, 200)

    def test_create_contract_from_request_requires_add_contract(self):
        for view_cls, path, kwargs in (
            (ContractRequestCreateContractView, '/contract/contract-request/contract-create/1', {'id': 1}),
            (ContractCreateView, '/contract/contract-request/contract-create/1/', {'contract_request_id': 1}),
        ):
            with self.subTest(view=view_cls.__name__), patch.object(view_cls, 'put', return_value=Response({})):
                view = view_cls.as_view()
                self.assertEqual(self._call(view, 'put', path, self.request_changer, **kwargs).status_code, 403)
                self.assertEqual(self._call(view, 'put', path, self.contract_adder, **kwargs).status_code, 403)
                self.assertEqual(
                    self._call(view, 'put', path, self.request_and_contract_creator, **kwargs).status_code, 200,
                )


class RelatedModuleScopeTestCase(TestCase):
    """La lectura per mòdul relacionat només val per al llistat i el detall (i
    les dades mínimes del contracte), no per a l'historial ni les exportacions;
    l'acció `permissions` ho reflecteix a `can_view`."""

    @classmethod
    def setUpTestData(cls):
        cls.invoice_viewer = _user('invoice-viewer-scope-2646', 'billing.view_invoice')
        cls.pricing_viewer = _user('pricing-viewer-scope-2646', 'pricing.view_pricerate')
        cls.contract_viewer = _user('contract-viewer-scope-2646', 'contract.view_contract')
        cls.request_viewer = _user('request-viewer-scope-2646', 'contract.view_contractrequest')
        cls.factory = APIRequestFactory()

    def _call(self, view, method, path, user, data=None, **kwargs):
        request = getattr(self.factory, method)(path, data or {}, format='json')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return view(request, **kwargs)

    def test_contract_logs_and_export_need_view_contract(self):
        for name, path in (('logs', '/contract/contract/1/logs/'), ('export_csv', '/contract/contract/export/excel/')):
            with self.subTest(action=name), patch.object(ContractViewSet, name, return_value=Response({})):
                view = ContractViewSet.as_view({'get': name})
                self.assertEqual(self._call(view, 'get', path, self.invoice_viewer, pk=1).status_code, 403)
                self.assertEqual(self._call(view, 'get', path, self.contract_viewer, pk=1).status_code, 200)

    def test_contract_minimal_from_related_module(self):
        with patch.object(ContractViewSet, 'get_minimal', return_value=Response({})):
            view = ContractViewSet.as_view({'get': 'get_minimal'})
            path = '/contract/contract/1/minimal/'
            self.assertEqual(self._call(view, 'get', path, self.invoice_viewer, pk=1).status_code, 200)
            self.assertEqual(self._call(view, 'get', path, self.pricing_viewer, pk=1).status_code, 403)

    def test_contract_request_other_reads_need_view_contractrequest(self):
        with patch.object(ContractRequestViewSet, 'validate_data', return_value=Response({})):
            view = ContractRequestViewSet.as_view({'get': 'validate_data'})
            path = '/contract/contract-request/1/validate-data/'
            self.assertEqual(self._call(view, 'get', path, self.invoice_viewer, pk=1).status_code, 403)
            self.assertEqual(self._call(view, 'get', path, self.request_viewer, pk=1).status_code, 200)

    def test_permissions_actions_report_related_read(self):
        for viewset, path in (
            (ContractViewSet, '/contract/contract/permissions/'),
            (ConsumptionManagementViewSet, '/contract/consumption-management/permissions/'),
        ):
            view = viewset.as_view({'get': 'permissions'})
            with self.subTest(path=path):
                data = self._call(view, 'get', path, self.invoice_viewer).data
                self.assertTrue(data['can_view'])
                self.assertFalse(data['can_change'])
                self.assertFalse(self._call(view, 'get', path, self.pricing_viewer).data['can_view'])

    def test_consumption_management_list_from_related_module(self):
        view = ConsumptionManagementViewSet.as_view({'get': 'list'})
        with patch('contract.views.consumption_management_view._get_fire_usage_token', return_value=[]), \
             patch('contract.views.consumption_management_view._get_fire_hydrant_items', return_value=[]), \
             patch('contract.views.consumption_management_view._get_inactive_consumption_items', return_value=[]), \
             patch('contract.views.consumption_management_view._get_duplicate_readings_items', return_value=[]):
            response = self._call(view, 'get', '/contract/consumption-management/', self.invoice_viewer)
        self.assertEqual(response.status_code, 200)


@patch('contract.views.contract_pdf_view.get_contract_pdf_filename', return_value='doc.pdf')
@patch('contract.views.contract_pdf_view.generate_contract_pdf_bytes', return_value=b'%PDF-1.4')
@patch('contract.views.contract_pdf_view.default_storage')
@patch('contract.views.contract_pdf_view.get_object_or_404', return_value=ContractRequest())
class ContractPdfDownloadTestCase(TestCase):
    """El PDF es comprova amb el registre que es genera i una descàrrega de
    només lectura no desa res a la sol·licitud."""

    @classmethod
    def setUpTestData(cls):
        cls.request_viewer = _user('request-viewer-pdf-2646', 'contract.view_contractrequest')
        cls.request_and_contract_viewer = _user(
            'request-contract-viewer-pdf-2646', 'contract.view_contractrequest', 'contract.view_contract',
        )
        cls.invoice_viewer = _user('invoice-viewer-pdf-2646', 'billing.view_invoice')
        cls.factory = APIRequestFactory()

    def _get(self, user):
        request = self.factory.get('/contract/download/1/')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return ReportPDFDownloadViewSet.as_view()(request, id=1)

    def test_request_with_contract_needs_view_contract(self, _get_request, storage, _generate, _filename):
        storage.save.return_value = 'tmp/contract_docs/doc.pdf'
        storage.url.return_value = '/media/tmp/contract_docs/doc.pdf'
        with patch.object(Contract.objects, 'get', return_value=Contract()):
            self.assertEqual(self._get(self.request_viewer).status_code, 403)
            self.assertEqual(self._get(self.request_and_contract_viewer).status_code, 200)
            self.assertEqual(self._get(self.invoice_viewer).status_code, 200)

    def test_read_only_download_does_not_save_request(self, _get_request, storage, _generate, _filename):
        storage.save.return_value = 'tmp/contract_docs/doc.pdf'
        storage.url.return_value = '/media/tmp/contract_docs/doc.pdf'
        with patch.object(Contract.objects, 'get', side_effect=Contract.DoesNotExist), \
             patch.object(FieldFile, 'save') as field_save:
            for user in (self.request_viewer, self.invoice_viewer):
                with self.subTest(user=user.username):
                    self.assertEqual(self._get(user).status_code, 200)
        field_save.assert_not_called()
