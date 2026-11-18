"""Permisos de les vistes de persones (#2654) i del catàleg MainPermission (#2646).

- Persones: GET requereix `view_person` (abans `DjangoModelPermissions` no
  exigia res per GET) i l'escriptura, add/change/delete. Qui pot llegir un
  mòdul relacionat (p. ex. `billing.view_invoice`) també pot consultar el
  llistat i el detall, però no els logs ni escriure.
- MainPermission: el llegeix qualsevol usuari autenticat (pantalles de grups),
  però només el superusuari canònic el pot modificar.
"""
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from auth.roles import CANONICAL_SUPERUSER_USERNAME
from coredata.models import MainPermission
from coredata.views.main_permission_view import MainPermissionViewSet
from coredata.views.person_view import PersonViewSet


def _perm(label):
    app_label, codename = label.split('.')
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class ViewPermissionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.no_perms = User.objects.create_user('no-perms-2654', 'no-perms-2654@example.com', 'x')
        cls.person_viewer = User.objects.create_user('person-viewer-2654', 'person-viewer-2654@example.com', 'x')
        cls.person_viewer.user_permissions.add(_perm('coredata.view_person'))
        cls.all_main_perms = User.objects.create_user('main-perms-2646', 'main-perms-2646@example.com', 'x')
        cls.all_main_perms.user_permissions.add(
            _perm('coredata.add_mainpermission'),
            _perm('coredata.change_mainpermission'),
            _perm('coredata.delete_mainpermission'),
        )
        cls.admin = User.objects.create_user('admin-2646', 'admin-2646@example.com', 'x', is_staff=True)
        cls.residual_superuser = User.objects.create_superuser('other-super-2646', 'other-super-2646@example.com', 'x')
        cls.superuser = User.objects.filter(username=CANONICAL_SUPERUSER_USERNAME).first() or \
            User.objects.create_superuser(CANONICAL_SUPERUSER_USERNAME, 'customers-2646@example.com', 'x')
        cls.main_permission = MainPermission.objects.create(
            name='test-2646', view_key='view_test_2646', change_key='change_test_2646',
            affected_models='coredata.person',
        )
        cls.factory = APIRequestFactory()

    def _call(self, view, method, path, user, data=None, **kwargs):
        request = getattr(self.factory, method)(path, data or {}, format='json')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return view(request, **kwargs)

    # Persones

    def test_person_list_and_detail_require_view_person(self):
        list_view = PersonViewSet.as_view({'get': 'list'})
        self.assertEqual(self._call(list_view, 'get', '/coredata/person/', self.no_perms).status_code, 403)
        self.assertEqual(self._call(list_view, 'get', '/coredata/person/', self.person_viewer).status_code, 200)
        detail_view = PersonViewSet.as_view({'get': 'retrieve'})
        self.assertEqual(self._call(detail_view, 'get', '/coredata/person/1/', self.no_perms, pk=1).status_code, 403)

    def test_person_read_from_related_module(self):
        invoice_viewer = User.objects.create_user('invoice-viewer-2654', 'invoice-viewer-2654@example.com', 'x')
        invoice_viewer.user_permissions.add(_perm('billing.view_invoice'))
        pricing_viewer = User.objects.create_user('pricing-viewer-2654', 'pricing-viewer-2654@example.com', 'x')
        pricing_viewer.user_permissions.add(_perm('pricing.view_pricerate'))
        list_view = PersonViewSet.as_view({'get': 'list'})
        self.assertEqual(self._call(list_view, 'get', '/coredata/person/', invoice_viewer).status_code, 200)
        self.assertEqual(self._call(list_view, 'get', '/coredata/person/', pricing_viewer).status_code, 403)
        create_view = PersonViewSet.as_view({'post': 'create'})
        self.assertEqual(self._call(create_view, 'post', '/coredata/person/', invoice_viewer).status_code, 403)

    def test_person_write_requires_write_permissions(self):
        create_view = PersonViewSet.as_view({'post': 'create'})
        for user in (self.no_perms, self.person_viewer):
            with self.subTest(user=user.username):
                self.assertEqual(self._call(create_view, 'post', '/coredata/person/', user).status_code, 403)
        update_view = PersonViewSet.as_view({'patch': 'partial_update'})
        self.assertEqual(
            self._call(update_view, 'patch', '/coredata/person/1/', self.person_viewer, pk=1).status_code, 403,
        )

    def test_person_head_like_get(self):
        invoice_viewer = User.objects.create_user('invoice-viewer-head-2654', 'invoice-viewer-head-2654@example.com', 'x')
        invoice_viewer.user_permissions.add(_perm('billing.view_invoice'))
        list_view = PersonViewSet.as_view({'get': 'list'})
        self.assertEqual(self._call(list_view, 'head', '/coredata/person/', self.no_perms).status_code, 403)
        for user in (self.person_viewer, invoice_viewer):
            with self.subTest(user=user.username):
                self.assertEqual(self._call(list_view, 'head', '/coredata/person/', user).status_code, 200)

    def test_person_logs_not_readable_from_related_module(self):
        invoice_viewer = User.objects.create_user('invoice-viewer-logs-2654', 'invoice-viewer-logs-2654@example.com', 'x')
        invoice_viewer.user_permissions.add(_perm('billing.view_invoice'))
        logs_view = PersonViewSet.as_view({'get': 'logs'})
        self.assertEqual(self._call(logs_view, 'get', '/coredata/person/1/logs/', invoice_viewer, pk=1).status_code, 403)

    def test_person_permissions_action_reports_related_read(self):
        invoice_viewer = User.objects.create_user('invoice-viewer-perms-2654', 'invoice-viewer-perms-2654@example.com', 'x')
        invoice_viewer.user_permissions.add(_perm('billing.view_invoice'))
        view = PersonViewSet.as_view({'get': 'permissions'})
        path = '/coredata/person/permissions/'
        data = self._call(view, 'get', path, invoice_viewer).data
        self.assertTrue(data['can_view'])
        self.assertFalse(data['can_change'])
        self.assertFalse(self._call(view, 'get', path, self.no_perms).data['can_view'])

    def test_person_permissions_action_open(self):
        view = PersonViewSet.as_view({'get': 'permissions'})
        self.assertEqual(self._call(view, 'get', '/coredata/person/permissions/', self.no_perms).status_code, 200)

    # MainPermission

    def test_main_permission_readable_by_authenticated(self):
        view = MainPermissionViewSet.as_view({'get': 'list'})
        self.assertEqual(self._call(view, 'get', '/coredata/main-permission/', self.no_perms).status_code, 200)

    def test_main_permission_write_only_canonical_superuser(self):
        update_view = MainPermissionViewSet.as_view({'patch': 'partial_update'})
        create_view = MainPermissionViewSet.as_view({'post': 'create'})
        delete_view = MainPermissionViewSet.as_view({'delete': 'destroy'})
        pk = self.main_permission.pk
        path = f'/coredata/main-permission/{pk}/'
        for user in (self.no_perms, self.all_main_perms, self.admin, self.residual_superuser):
            with self.subTest(user=user.username):
                self.assertEqual(
                    self._call(update_view, 'patch', path, user, {'is_default': True}, pk=pk).status_code, 403,
                )
                self.assertEqual(
                    self._call(create_view, 'post', '/coredata/main-permission/', user, {'name': 'x'}).status_code,
                    403,
                )
                self.assertEqual(self._call(delete_view, 'delete', path, user, pk=pk).status_code, 403)
        self.main_permission.refresh_from_db()
        self.assertFalse(self.main_permission.is_default)

        response = self._call(update_view, 'patch', path, self.superuser, {'all_recommended': True}, pk=pk)
        self.assertEqual(response.status_code, 200)
        self.main_permission.refresh_from_db()
        self.assertTrue(self.main_permission.all_recommended)
