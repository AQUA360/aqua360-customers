"""Permisos de les vistes de Verifactu (#2661).

Abans qualsevol usuari autenticat podia llegir, crear, modificar i eliminar
notificacions i lots de Verifactu. Ara es governen amb els permisos de factura
(com l'acció `permissions` que fa servir el frontend): llegir requereix
`view_invoice` i notificar una factura, `change_invoice`. Les notificacions i
els lots no es poden crear, modificar ni eliminar per l'API.
"""
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from verifactu.views import VerifactuBatchViewSet, VerifactuNotificationViewSet


def _perm(label):
    app_label, codename = label.split('.')
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class VerifactuViewPermissionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.no_perms = User.objects.create_user('no-perms-2661', 'no-perms-2661@example.com', 'x')
        cls.invoice_viewer = User.objects.create_user('invoice-viewer-2661', 'invoice-viewer-2661@example.com', 'x')
        cls.invoice_viewer.user_permissions.add(_perm('billing.view_invoice'))
        cls.invoice_editor = User.objects.create_user('invoice-editor-2661', 'invoice-editor-2661@example.com', 'x')
        cls.invoice_editor.user_permissions.add(_perm('billing.view_invoice'), _perm('billing.change_invoice'))
        cls.factory = APIRequestFactory()

    def _call(self, view, method, path, user, **kwargs):
        request = getattr(self.factory, method)(path, {}, format='json')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return view(request, **kwargs)

    def test_lists_require_view_invoice(self):
        for viewset, path in (
            (VerifactuNotificationViewSet, '/verifactu/notification/'),
            (VerifactuBatchViewSet, '/verifactu/batch/'),
        ):
            view = viewset.as_view({'get': 'list'})
            with self.subTest(path=path):
                self.assertEqual(self._call(view, 'get', path, self.no_perms).status_code, 403)
                self.assertEqual(self._call(view, 'get', path, self.invoice_viewer).status_code, 200)

    def test_detail_and_logs_require_view_invoice(self):
        detail_view = VerifactuNotificationViewSet.as_view({'get': 'retrieve'})
        logs_view = VerifactuNotificationViewSet.as_view({'get': 'logs'})
        self.assertEqual(self._call(detail_view, 'get', '/verifactu/notification/1/', self.no_perms, pk=1).status_code, 403)
        self.assertEqual(self._call(logs_view, 'get', '/verifactu/notification/1/logs/', self.no_perms, pk=1).status_code, 403)
        batch_view = VerifactuBatchViewSet.as_view({'get': 'retrieve'})
        self.assertEqual(self._call(batch_view, 'get', '/verifactu/batch/1/', self.no_perms, pk=1).status_code, 403)

    def test_no_generic_write_endpoints(self):
        for viewset in (VerifactuNotificationViewSet, VerifactuBatchViewSet):
            for name in ('create', 'update', 'partial_update', 'destroy'):
                with self.subTest(viewset=viewset.__name__, action=name):
                    self.assertFalse(hasattr(viewset, name))

    def test_notify_requires_change_invoice(self):
        view = VerifactuNotificationViewSet.as_view({'put': 'notify_verifactu'})
        path = '/verifactu/notification/0/notify-verifactu/'
        self.assertEqual(self._call(view, 'put', path, self.no_perms, invoice_id='0').status_code, 403)
        self.assertEqual(self._call(view, 'put', path, self.invoice_viewer, invoice_id='0').status_code, 403)
        # Amb permís passa la comprovació i respon que la factura no existeix.
        self.assertEqual(self._call(view, 'put', path, self.invoice_editor, invoice_id='0').status_code, 404)

    def test_permissions_action_open(self):
        view = VerifactuNotificationViewSet.as_view({'get': 'permissions'})
        self.assertEqual(
            self._call(view, 'get', '/verifactu/notification/permissions/', self.no_perms).status_code, 200,
        )
