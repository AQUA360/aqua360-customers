# auth/tests.py
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
import json

class LoginTest(TestCase):
    token = None  # Variable de clase para almacenar el token

    def setUp(self):
        # Crea un usuari de prova per al test
        self.username = 'customers'
        self.password = 'customers'
        self.user = User.objects.create_user(username=self.username, password=self.password)

    def test_login(self):
        print('test_login: ', self)
        # URL de login (canvia-ho si has personalitzat la URL de login)
        login_url = reverse('login')
        
        # Dades de login
        data = {
            'username': self.username,
            'password': self.password,
        }
        
        # Fa una petició POST amb les dades de login
        response = self.client.post(login_url, data)
        
        # Comprova si s'ha redirigit a la pàgina d'inici de sessió correctament (200 OK)
        self.assertEqual(response.status_code, 200)
        
        # print(response.content.decode('utf-8')) # {"username":"usuari_de_prova","token":"7b21d0b21ac28cd8721688b5db7d484adc32101f","tenants":[]}

        # Verificar la presència del token en la resposta
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIn('token', response_data)
        
        # Obtindre el valor del token
        received_token = response_data.get('token')
        print(received_token)
        self.__class__.token = received_token

    def test_token(self):
        print('test_token: ', self)
    
        if self.__class__.token is None:
            self.fail("No se encontró ningún token guardado")
        
        print(self.__class__.token)
        


from django.contrib.auth.models import Group, Permission
from rest_framework.test import APIClient

from coredata.models import MainPermission


class UserManagementPermissionTest(TestCase):
    """Gestió d'usuaris i grups: lectura per autenticats, escriptura només superusuari."""

    def setUp(self):
        MainPermission.objects.update_or_create(
            name="users",
            defaults={
                "view_key": "view_user",
                "change_key": "change_user",
                "affected_models": "auth.user,auth.group,auth.permission",
                "change_requires_superuser": True,
            },
        )
        MainPermission.objects.get_or_create(
            name="default",
            defaults={
                "view_key": "view_default",
                "change_key": "change_default",
                "affected_models": "notification.notification",
                "is_default": True,
            },
        )
        self.client = APIClient()
        self.superuser = User.objects.create_superuser("customers", "customers@example.com", "customers-pwd")
        self.plain = User.objects.create_user("plain", "plain@example.com", "plain-pwd")
        self.viewer = User.objects.create_user("viewer", "viewer@example.com", "viewer-pwd")
        self.viewer.user_permissions.add(Permission.objects.get(codename="view_user"))
        # Admin de grup: té change_user a Django, però no és superusuari.
        self.admin = User.objects.create_user("admin", "admin@example.com", "admin-pwd")
        self.admin.user_permissions.add(
            Permission.objects.get(codename="view_user"),
            Permission.objects.get(codename="change_user"),
            Permission.objects.get(codename="change_group"),
        )
        self.group = Group.objects.create(name="group-test")
        self.privileged_group = Group.objects.create(name="privileged")
        self.privileged_group.permissions.add(
            Permission.objects.get(codename="view_user"),
            Permission.objects.get(codename="change_user"),
            Permission.objects.get(codename="add_user"),
            Permission.objects.get(codename="delete_user"),
        )

    def test_user_without_permission_cannot_change_other_password(self):
        self.client.force_authenticate(self.plain)
        response = self.client.patch(f"/auth/user/{self.superuser.id}/", {"new_pwd": "hacked"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password("customers-pwd"))

    def test_authenticated_user_can_list_users_and_groups_for_selection(self):
        """Calendar, daily-document, etc. necessiten GET sense view_user."""
        self.client.force_authenticate(self.plain)
        self.assertEqual(self.client.get("/auth/user/").status_code, 200)
        self.assertEqual(self.client.get("/auth/group/").status_code, 200)
        self.assertEqual(self.client.patch(f"/auth/user/{self.plain.id}/", {"first_name": "X"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(f"/auth/user/{self.plain.id}/").status_code, 403)

    def test_viewer_can_list_but_not_modify(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get("/auth/user/").status_code, 200)
        response = self.client.patch(f"/auth/user/{self.plain.id}/", {"first_name": "X"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(f"/auth/user/{self.plain.id}/").status_code, 403)

    def test_admin_cannot_change_password_or_group_even_with_change_user(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/auth/user/{self.plain.id}/",
            {"new_pwd": "hacked", "group_id": self.privileged_group.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.plain.refresh_from_db()
        self.assertTrue(self.plain.check_password("plain-pwd"))
        self.assertFalse(self.plain.groups.filter(id=self.privileged_group.id).exists())

        self.assertEqual(self.client.delete(f"/auth/user/{self.plain.id}/").status_code, 403)
        self.assertTrue(User.objects.filter(id=self.plain.id).exists())

    def test_admin_cannot_self_assign_privileged_group(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/auth/user/{self.admin.id}/",
            {"group_id": self.privileged_group.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.groups.filter(id=self.privileged_group.id).exists())

    def test_change_user_permission_flag_false_for_non_superuser(self):
        from auth.permissions import PermissionManager
        self.assertFalse(PermissionManager.has_permission(self.admin, 'change_user'))
        self.assertTrue(PermissionManager.has_permission(self.admin, 'view_user'))
        self.assertTrue(PermissionManager.has_permission(self.superuser, 'change_user'))

    def test_superuser_can_modify_user_and_password(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(
            f"/auth/user/{self.plain.id}/",
            {"new_pwd": "riu-blau-2026", "first_name": "Nou", "group_id": self.group.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.plain.refresh_from_db()
        self.assertTrue(self.plain.check_password("riu-blau-2026"))
        self.assertEqual(self.plain.first_name, "Nou")
        self.assertTrue(self.plain.groups.filter(id=self.group.id).exists())

    def test_superuser_can_set_admin_or_group_role(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(
            f"/auth/user/{self.plain.id}/",
            {"role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.plain.refresh_from_db()
        self.assertFalse(self.plain.is_superuser)
        self.assertTrue(self.plain.is_staff)
        self.assertFalse(self.plain.groups.exists())

        response = self.client.patch(
            f"/auth/user/{self.plain.id}/",
            {"role": "none", "group_id": self.group.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.plain.refresh_from_db()
        self.assertFalse(self.plain.is_superuser)
        self.assertFalse(self.plain.is_staff)
        self.assertTrue(self.plain.groups.filter(id=self.group.id).exists())

    def test_non_customers_cannot_be_superuser(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(
            f"/auth/user/{self.plain.id}/",
            {"role": "superuser"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.plain.refresh_from_db()
        self.assertFalse(self.plain.is_superuser)

    def test_admin_has_all_perms_except_user_management_write(self):
        from auth.permissions import PermissionManager
        self.admin.is_staff = True
        self.admin.save(update_fields=['is_staff'])
        self.assertTrue(PermissionManager.has_permission(self.admin, 'view_default'))
        self.assertTrue(PermissionManager.has_permission(self.admin, 'change_default'))
        self.assertTrue(PermissionManager.has_permission(self.admin, 'view_user'))
        self.assertFalse(PermissionManager.has_permission(self.admin, 'change_user'))
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/auth/user/").status_code, 200)
        self.assertEqual(self.client.get("/auth/group/").status_code, 200)

    def test_admin_cannot_change_user_role(self):
        self.admin.is_staff = True
        self.admin.save(update_fields=['is_staff'])
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f"/auth/user/{self.plain.id}/",
            {"role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_cannot_demote_customers_superuser(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(
            f"/auth/user/{self.superuser.id}/",
            {"role": "admin"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_superuser)

    def test_cannot_delete_customers_superuser(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.delete(f"/auth/user/{self.superuser.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(User.objects.filter(id=self.superuser.id).exists())

    def test_admin_model_perms_block_user_mgmt_write_both_arg_orders(self):
        from auth.permissions import PermissionManager
        self.admin.is_staff = True
        self.admin.save(update_fields=['is_staff'])
        for args in (('user', 'auth'), ('auth', 'user'), ('group', 'auth'), ('auth', 'group')):
            perms = PermissionManager.get_model_permissions(self.admin, *args)
            self.assertTrue(perms['can_view'], args)
            self.assertFalse(perms['can_add'], args)
            self.assertFalse(perms['can_change'], args)
            self.assertFalse(perms['can_delete'], args)
        invoice_perms = PermissionManager.get_model_permissions(self.admin, 'invoice', 'billing')
        self.assertTrue(invoice_perms['can_view'])
        self.assertTrue(invoice_perms['can_change'])

    def test_group_write_requires_superuser(self):
        self.client.force_authenticate(self.plain)
        self.assertEqual(self.client.delete(f"/auth/group/{self.group.id}/").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"/auth/group/{self.group.id}/").status_code, 403)
        self.assertEqual(
            self.client.patch(
                f"/auth/group/{self.group.id}/",
                {"name": "hacked", "user_ids": [], "permissions_data": []},
                format="json",
            ).status_code,
            403,
        )
        self.assertTrue(Group.objects.filter(id=self.group.id).exists())

        self.client.force_authenticate(self.superuser)
        self.assertEqual(self.client.delete(f"/auth/group/{self.group.id}/").status_code, 204)
        self.assertFalse(Group.objects.filter(id=self.group.id).exists())

    def test_group_cannot_receive_user_management_write_perms(self):
        from auth.utils import manage_group_permissions

        manage_group_permissions(self.group, [{
            'viewKey': 'view_user',
            'changeKey': 'change_user',
            'hasView': True,
            'hasChange': True,
        }])
        codenames = set(self.group.permissions.values_list('codename', flat=True))
        self.assertIn('view_user', codenames)
        self.assertNotIn('change_user', codenames)
        self.assertNotIn('add_user', codenames)
        self.assertNotIn('delete_user', codenames)

    def test_permissions_action_only_requires_authentication(self):
        self.client.force_authenticate(self.plain)
        self.assertEqual(self.client.get("/auth/user/permissions/").status_code, 200)
        self.assertEqual(self.client.get("/auth/group/permissions/").status_code, 200)

    def test_admin_role_django_has_perm_for_business_get(self):
        """is_staff admin recupera has_perm de negoci (DRF permissions usen has_perm)."""
        staff_admin = User.objects.create_user("staff-admin", "staff@example.com", "pwd", is_staff=True)
        staff_admin = User.objects.get(pk=staff_admin.pk)  # refresca cache de backends
        self.assertTrue(staff_admin.has_perm('service.view_exploitation'))
        self.assertTrue(staff_admin.has_perm('order.view_order'))
        self.assertTrue(staff_admin.has_perm('billing.view_billing'))
        self.assertTrue(staff_admin.has_perm('auth.view_user'))
        self.assertFalse(staff_admin.has_perm('auth.change_user'))
        self.assertFalse(staff_admin.has_perm('auth.add_group'))
        self.assertFalse(staff_admin.has_perm('auth.delete_permission'))
        # Sense is_staff, has_perm de negoci no ve del backend d'admin
        self.assertFalse(self.plain.has_perm('service.view_exploitation'))

    def test_admin_can_get_exploitation_site_and_daily_document_pending(self):
        staff_admin = User.objects.create_user("staff-get", "staff-get@example.com", "pwd", is_staff=True)
        self.client.force_authenticate(staff_admin)
        self.assertEqual(self.client.get("/service/exploitation-site/").status_code, 200)
        # pending pot fallar per ConfigProject absent → 500; no ha de ser 403
        pending = self.client.get("/statistics/daily-document/pending/")
        self.assertNotEqual(pending.status_code, 403)


class LoginBruteForceProtectionTest(TestCase):
    """El login no admet intents il·limitats: límit per IP i bloqueig per usuari."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(username='victima', password='correcta')
        self.url = reverse('login')

    def _login(self, username, password, ip='10.0.0.1'):
        return self.client.post(
            self.url, {'username': username, 'password': password},
            REMOTE_ADDR=ip,
        )

    def test_user_locked_after_failed_attempts_even_with_correct_password(self):
        from django.conf import settings
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self.assertEqual(self._login('victima', 'incorrecta').status_code, 400)
        # Des d'una altra IP, l'usuari ja queda bloquejat (també amb la contrasenya bona)
        self.assertEqual(self._login('victima', 'correcta', ip='10.0.0.2').status_code, 429)

    def test_failed_attempts_are_recorded(self):
        from axes.models import AccessAttempt
        self._login('victima', 'incorrecta')
        self.assertTrue(AccessAttempt.objects.filter(username='victima').exists())

    def test_ip_throttled_across_different_usernames(self):
        from unittest import mock
        from rest_framework.throttling import ScopedRateThrottle
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'login': '3/min'}):
            codes = [self._login(f'usuari{i}', 'x').status_code for i in range(4)]
        self.assertEqual(codes[:3], [400, 400, 400])
        self.assertEqual(codes[3], 429)

    def test_ip_quota_shared_between_token_and_anonymous_requests(self):
        from unittest import mock
        from rest_framework.throttling import ScopedRateThrottle
        token = self._login('victima', 'correcta').json()['token']
        from django.core.cache import cache
        cache.clear()
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'login': '3/min'}):
            codes = []
            for i in range(4):
                extra = {'HTTP_AUTHORIZATION': f'Token {token}'} if i % 2 else {}
                codes.append(self.client.post(
                    self.url, {'username': f'u{i}', 'password': 'x'},
                    REMOTE_ADDR='10.0.0.9', **extra,
                ).status_code)
        # Amb i sense token comparteixen la mateixa quota per IP
        self.assertEqual(codes[3], 429)

    def test_ip_taken_from_forwarded_for_behind_cloudflare_and_nginx(self):
        """Amb Cloudflare + nginx, X-Forwarded-For és «client, cloudflare»: el límit és per client."""
        from unittest import mock
        from rest_framework.throttling import ScopedRateThrottle

        def login(forwarded):
            return self.client.post(
                self.url, {'username': 'x', 'password': 'x'},
                REMOTE_ADDR='172.16.0.1', HTTP_X_FORWARDED_FOR=forwarded,
            ).status_code

        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', {'login': '2/min'}):
            self.assertEqual(login('203.0.113.1, 198.51.100.7'), 400)
            # Un valor inventat pel client davant de la cadena no li canvia la quota
            self.assertEqual(login('192.0.2.99, 203.0.113.1, 198.51.100.7'), 400)
            self.assertEqual(login('203.0.113.1, 198.51.100.7'), 429)
            # Un altre client per la mateixa porta de Cloudflare no queda afectat
            self.assertEqual(login('203.0.113.2, 198.51.100.7'), 400)

    def test_successful_login_is_not_blocked(self):
        resp = self._login('victima', 'correcta')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.json())

    def test_admin_login_locks_user(self):
        from django.conf import settings
        admin_url = reverse('admin:login')
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self.client.post(admin_url, {'username': 'victima', 'password': 'mala'}, REMOTE_ADDR='10.0.0.3')
        resp = self.client.post(admin_url, {'username': 'victima', 'password': 'correcta'}, REMOTE_ADDR='10.0.0.3')
        self.assertEqual(resp.status_code, 429)


class PasswordValidationTest(TestCase):
    """Les contrasenyes creades o canviades per l'API passen els validadors; els superusuaris, a més, la regla forta."""

    def setUp(self):
        MainPermission.objects.get_or_create(
            name="users",
            defaults={"view_key": "view_user", "change_key": "change_user",
                      "affected_models": "auth.user,auth.group,auth.permission"},
        )
        self.client = APIClient()
        self.superuser = User.objects.create_superuser("customers", "customers@example.com", "customers-pwd")
        self.plain = User.objects.create_user("plain", "plain@example.com", "plain-pwd")
        self.client.force_authenticate(self.superuser)

    def create_user(self, password, role="none"):
        return self.client.post("/auth/user/", {
            "username": "nou", "email": "nou@example.com",
            "new_pwd": password, "role": role,
        }, format="json")

    def test_weak_password_rejected_on_create(self):
        for password in ("a", "12345678", "password"):
            response = self.create_user(password)
            self.assertEqual(response.status_code, 400, password)
            self.assertIn("new_pwd", response.data)
        self.assertFalse(User.objects.filter(username="nou").exists())

    def test_weak_password_rejected_on_update(self):
        response = self.client.patch(f"/auth/user/{self.plain.id}/", {"new_pwd": "1"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.plain.refresh_from_db()
        self.assertTrue(self.plain.check_password("plain-pwd"))

    def test_regular_user_needs_a_number_but_not_special_character(self):
        response = self.create_user("riublaucel")
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_pwd", response.data)
        self.assertEqual(self.create_user("riublau2026").status_code, 201)

    def test_superuser_needs_letters_numbers_and_special_character(self):
        # Només `customers` pot ser superuser; es valida amb un canvi de contrasenya seu.
        for password in ("riublau2026", "riu-blau-cel", "2026-2027-28"):
            response = self.client.patch(
                f"/auth/user/{self.superuser.id}/", {"new_pwd": password}, format="json")
            self.assertEqual(response.status_code, 400, password)
        response = self.client.patch(
            f"/auth/user/{self.superuser.id}/", {"new_pwd": "riu-blau-2026"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password("riu-blau-2026"))

    def test_promoting_to_superuser_is_forbidden_for_non_customers(self):
        response = self.client.patch(
            f"/auth/user/{self.plain.id}/",
            {"role": "superuser", "new_pwd": "riu-blau-2026"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.plain.refresh_from_db()
        self.assertFalse(self.plain.is_superuser)
        self.assertTrue(self.plain.check_password("plain-pwd"))

    def test_existing_superuser_not_affected_without_password_change(self):
        response = self.client.patch(
            f"/auth/user/{self.superuser.id}/", {"first_name": "Nou"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.check_password("customers-pwd"))
        self.assertEqual(self.superuser.first_name, "Nou")


class GroupPermissionsTest(TestCase):
    """Comprovacions de permisos de grups amb els arguments en l'ordre correcte i permissions_data validades."""

    def setUp(self):
        MainPermission.objects.get_or_create(
            name="users",
            defaults={
                "view_key": "view_user",
                "change_key": "change_user",
                "affected_models": "auth.user,auth.group,auth.permission",
                "is_default": True,
            },
        )
        self.client = APIClient()
        self.superuser = User.objects.create_superuser("customers", "customers@example.com", "customers-pwd")
        self.manager = User.objects.create_user("manager", "manager@example.com", "manager-pwd")
        self.manager.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="auth", codename__in=["view_user", "change_user", "view_group", "change_group", "add_group"]))

    def test_model_permissions_use_model_then_app(self):
        from auth.permissions import PermissionManager
        permissions = PermissionManager.get_model_permissions(self.manager, "group", "auth")
        self.assertTrue(permissions["can_view"])
        self.assertTrue(permissions["can_change"])
        self.assertFalse(permissions["can_delete"])

    def test_group_create_still_requires_superuser(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post("/auth/group/", {"name": "g", "user_ids": [], "permissions_data": []}, format="json")
        self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(self.superuser)
        response = self.client.post("/auth/group/", {"name": "g", "user_ids": [], "permissions_data": []}, format="json")
        self.assertEqual(response.status_code, 201)

    def test_malformed_permissions_data_returns_400(self):
        self.client.force_authenticate(self.superuser)
        for permissions_data in (["x"], [{"hasView": True}], [{"viewKey": "does_not_exist"}],
                                 [{"viewKey": "view_user", "affected_data": "x"}]):
            response = self.client.post(
                "/auth/group/", {"name": "g", "user_ids": [], "permissions_data": permissions_data}, format="json")
            self.assertEqual(response.status_code, 400, permissions_data)
        self.assertFalse(Group.objects.filter(name="g").exists())

    def test_valid_permissions_data_is_applied(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.post("/auth/group/", {
            "name": "g", "user_ids": [],
            "permissions_data": [{"viewKey": "view_user", "hasView": True, "hasChange": False}],
        }, format="json")
        self.assertEqual(response.status_code, 201)
        group = Group.objects.get(name="g")
        self.assertTrue(group.permissions.filter(codename="view_user").exists())


from django.test import override_settings


@override_settings(EXTRA_SUPERUSER_USERNAMES=["extra", "extra2"])
class ExtraSuperuserTest(TestCase):
    """Superusuaris addicionals de la configuració: gestionen usuaris, però només
    `customers` dona o treu el rol de superusuari i modifica la configuració."""

    def setUp(self):
        MainPermission.objects.update_or_create(
            name="users",
            defaults={
                "view_key": "view_user",
                "change_key": "change_user",
                "affected_models": "auth.user,auth.group,auth.permission",
                "change_requires_superuser": True,
            },
        )
        self.client = APIClient()
        self.customers = User.objects.create_superuser("customers", "customers@example.com", "customers-pwd")
        self.extra = User.objects.create_superuser("extra", "extra@example.com", "extra-pwd")
        self.extra2 = User.objects.create_user("extra2", "extra2@example.com", "extra2-pwd", is_staff=True)
        # is_superuser residual d'abans de separar admin i superuser: continua sent admin
        self.residual = User.objects.create_superuser("residual", "residual@example.com", "residual-pwd")
        self.plain = User.objects.create_user("plain", "plain@example.com", "plain-pwd")

    def test_roles(self):
        from auth.roles import get_user_role
        self.assertEqual(get_user_role(self.customers), "superuser")
        self.assertEqual(get_user_role(self.extra), "superuser")
        self.assertEqual(get_user_role(self.extra2), "admin")
        self.assertEqual(get_user_role(self.residual), "admin")

    def test_stale_request_cannot_restore_revoked_superuser(self):
        # La sessió encara té l'usuari d'abans de la revocació (is_superuser=True a memòria)
        stale_extra = User.objects.get(pk=self.extra.pk)
        User.objects.filter(pk=self.extra.pk).update(is_superuser=False, is_staff=True)
        self.client.force_authenticate(stale_extra)
        response = self.client.patch(
            f"/auth/user/{self.extra.id}/", {"first_name": "Extra", "role": "superuser"}, format="json",
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.extra.refresh_from_db()
        self.assertFalse(self.extra.is_superuser)

    def test_extra_superuser_can_create_and_modify_users(self):
        self.client.force_authenticate(self.extra)
        response = self.client.post(
            "/auth/user/",
            {"username": "nou", "email": "nou@example.com", "new_pwd": "riu-blau-2026", "role": "none"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        response = self.client.patch(
            f"/auth/user/{self.plain.id}/", {"role": "admin", "first_name": "Nou"}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.plain.refresh_from_db()
        self.assertTrue(self.plain.is_staff)

    def test_extra_superuser_can_manage_groups(self):
        self.client.force_authenticate(self.extra)
        response = self.client.post(
            "/auth/group/", {"name": "nou-grup", "user_ids": [], "permissions_data": []}, format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)

    def test_customers_can_grant_and_revoke_superuser_to_allowed_account(self):
        self.client.force_authenticate(self.customers)
        response = self.client.patch(f"/auth/user/{self.extra2.id}/", {"role": "superuser"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.extra2.refresh_from_db()
        self.assertTrue(self.extra2.is_superuser)
        self.assertEqual(response.data["role"], "superuser")

        response = self.client.patch(f"/auth/user/{self.extra2.id}/", {"role": "admin"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.extra2.refresh_from_db()
        self.assertFalse(self.extra2.is_superuser)

    def test_customers_cannot_grant_superuser_to_account_not_allowed(self):
        self.client.force_authenticate(self.customers)
        response = self.client.patch(f"/auth/user/{self.plain.id}/", {"role": "superuser"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.plain.refresh_from_db()
        self.assertFalse(self.plain.is_superuser)

    def test_extra_superuser_cannot_grant_superuser(self):
        self.client.force_authenticate(self.extra)
        response = self.client.patch(f"/auth/user/{self.extra2.id}/", {"role": "superuser"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.extra2.refresh_from_db()
        self.assertFalse(self.extra2.is_superuser)

        response = self.client.post(
            "/auth/user/",
            {"username": "extra3", "email": "extra3@example.com", "new_pwd": "Riu-blau-2026!", "role": "superuser"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="extra3").exists())

    def test_extra_superuser_cannot_revoke_own_superuser(self):
        self.client.force_authenticate(self.extra)
        response = self.client.patch(f"/auth/user/{self.extra.id}/", {"role": "admin"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.extra.refresh_from_db()
        self.assertTrue(self.extra.is_superuser)

    def test_extra_superuser_cannot_revoke_own_superuser_by_renaming(self):
        self.client.force_authenticate(self.extra)
        response = self.client.patch(f"/auth/user/{self.extra.id}/", {"username": "renamed"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.extra.refresh_from_db()
        self.assertEqual(self.extra.username, "extra")
        self.assertTrue(self.extra.is_superuser)

    def test_extra_superuser_cannot_delete_own_account(self):
        self.client.force_authenticate(self.extra)
        self.assertEqual(self.client.delete(f"/auth/user/{self.extra.id}/").status_code, 403)
        self.assertTrue(User.objects.filter(id=self.extra.id).exists())

    def test_customers_can_delete_extra_superuser(self):
        self.client.force_authenticate(self.customers)
        self.assertEqual(self.client.delete(f"/auth/user/{self.extra.id}/").status_code, 204)

    def test_extra_superuser_can_edit_own_data(self):
        self.client.force_authenticate(self.extra)
        response = self.client.patch(f"/auth/user/{self.extra.id}/", {"first_name": "Jo"}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.extra.refresh_from_db()
        self.assertTrue(self.extra.is_superuser)
        self.assertEqual(self.extra.first_name, "Jo")

    def test_extra_superuser_cannot_modify_or_delete_customers(self):
        self.client.force_authenticate(self.extra)
        response = self.client.patch(
            f"/auth/user/{self.customers.id}/", {"new_pwd": "Riu-blau-2026!"}, format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.customers.refresh_from_db()
        self.assertTrue(self.customers.check_password("customers-pwd"))
        self.assertEqual(self.client.delete(f"/auth/user/{self.customers.id}/").status_code, 403)

    def test_extra_superuser_cannot_modify_or_delete_other_superuser(self):
        self.extra2.is_superuser = True
        self.extra2.save(update_fields=["is_superuser"])
        self.client.force_authenticate(self.extra)
        response = self.client.patch(f"/auth/user/{self.extra2.id}/", {"first_name": "X"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(f"/auth/user/{self.extra2.id}/").status_code, 403)
        self.assertTrue(User.objects.filter(id=self.extra2.id).exists())

    def test_residual_superuser_cannot_manage_users(self):
        self.client.force_authenticate(self.residual)
        response = self.client.patch(f"/auth/user/{self.plain.id}/", {"first_name": "X"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_extra_superuser_cannot_edit_config_project_nor_main_permissions(self):
        from coredata.models import ConfigProject
        config = ConfigProject.objects.create(token="some_token", name="Some token", value="old")
        self.client.force_authenticate(self.extra)
        response = self.client.post(
            "/coredata/config-project/bulk-update-values/",
            [{"token": "some_token", "value": "new"}],
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        config.refresh_from_db()
        self.assertEqual(config.value, "old")

        main_permission = MainPermission.objects.get(name="users")
        response = self.client.patch(
            f"/coredata/main-permission/{main_permission.id}/", {"is_default": True}, format="json",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.customers)
        response = self.client.patch(
            f"/coredata/main-permission/{main_permission.id}/", {"is_default": False}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
