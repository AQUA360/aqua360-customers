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
    """Gestió d'usuaris i grups: lectura amb `view_user`, escriptura amb `change_user`."""

    def setUp(self):
        MainPermission.objects.get_or_create(
            name="users",
            defaults={
                "view_key": "view_user",
                "change_key": "change_user",
                "affected_models": "auth.user,auth.group,auth.permission",
            },
        )
        self.client = APIClient()
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pwd")
        self.plain = User.objects.create_user("plain", "plain@example.com", "plain-pwd")
        self.viewer = User.objects.create_user("viewer", "viewer@example.com", "viewer-pwd")
        self.viewer.user_permissions.add(Permission.objects.get(codename="view_user"))
        self.manager = User.objects.create_user("manager", "manager@example.com", "manager-pwd")
        self.manager.user_permissions.add(
            Permission.objects.get(codename="view_user"),
            Permission.objects.get(codename="change_user"),
        )
        self.group = Group.objects.create(name="group-test")

    def test_user_without_permission_cannot_change_other_password(self):
        self.client.force_authenticate(self.plain)
        response = self.client.patch(f"/auth/user/{self.admin.id}/", {"new_pwd": "hacked"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("admin-pwd"))

    def test_user_without_permission_cannot_list_users(self):
        self.client.force_authenticate(self.plain)
        self.assertEqual(self.client.get("/auth/user/").status_code, 403)

    def test_viewer_can_list_but_not_modify(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get("/auth/user/").status_code, 200)
        response = self.client.patch(f"/auth/user/{self.plain.id}/", {"first_name": "X"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(f"/auth/user/{self.plain.id}/").status_code, 403)

    def test_manager_can_modify_user_but_not_superuser(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(f"/auth/user/{self.plain.id}/", {"new_pwd": "riu-blau-2026"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.plain.refresh_from_db()
        self.assertTrue(self.plain.check_password("riu-blau-2026"))

        response = self.client.patch(f"/auth/user/{self.admin.id}/", {"new_pwd": "hacked"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(f"/auth/user/{self.admin.id}/").status_code, 403)
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())

    def test_superuser_can_modify_superuser(self):
        other_admin = User.objects.create_superuser("admin2", "admin2@example.com", "pwd")
        self.client.force_authenticate(self.admin)
        response = self.client.patch(f"/auth/user/{other_admin.id}/", {"first_name": "Nou"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_group_delete_requires_superuser(self):
        self.client.force_authenticate(self.plain)
        self.assertEqual(self.client.delete(f"/auth/group/{self.group.id}/").status_code, 403)
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.delete(f"/auth/group/{self.group.id}/").status_code, 403)
        self.assertTrue(Group.objects.filter(id=self.group.id).exists())

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f"/auth/group/{self.group.id}/").status_code, 204)
        self.assertFalse(Group.objects.filter(id=self.group.id).exists())

    def test_permissions_action_only_requires_authentication(self):
        self.client.force_authenticate(self.plain)
        self.assertEqual(self.client.get("/auth/user/permissions/").status_code, 200)
        self.assertEqual(self.client.get("/auth/group/permissions/").status_code, 200)


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
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pwd")
        self.plain = User.objects.create_user("plain", "plain@example.com", "plain-pwd")
        self.client.force_authenticate(self.admin)

    def create_user(self, password, is_superuser=False):
        return self.client.post("/auth/user/", {
            "username": "nou", "email": "nou@example.com",
            "new_pwd": password, "is_superuser": is_superuser,
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
        for password in ("riublau2026", "riu-blau-cel", "2026-2027-28"):
            response = self.create_user(password, is_superuser=True)
            self.assertEqual(response.status_code, 400, password)
        self.assertEqual(self.create_user("riu-blau-2026", is_superuser=True).status_code, 201)
        self.assertTrue(User.objects.get(username="nou").is_superuser)

    def test_promoting_to_superuser_applies_strong_rule_to_new_password(self):
        response = self.client.patch(
            f"/auth/user/{self.plain.id}/", {"is_superuser": True, "new_pwd": "riublau2026"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.plain.refresh_from_db()
        self.assertFalse(self.plain.is_superuser)

    def test_existing_superuser_not_affected_without_password_change(self):
        other_admin = User.objects.create_superuser("admin2", "admin2@example.com", "1")
        response = self.client.patch(f"/auth/user/{other_admin.id}/", {"first_name": "Nou"}, format="json")
        self.assertEqual(response.status_code, 200)
        other_admin.refresh_from_db()
        self.assertTrue(other_admin.check_password("1"))


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
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "admin-pwd")
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
        self.client.force_authenticate(self.admin)
        response = self.client.post("/auth/group/", {"name": "g", "user_ids": [], "permissions_data": []}, format="json")
        self.assertEqual(response.status_code, 201)

    def test_malformed_permissions_data_returns_400(self):
        self.client.force_authenticate(self.admin)
        for permissions_data in (["x"], [{"hasView": True}], [{"viewKey": "does_not_exist"}],
                                 [{"viewKey": "view_user", "affected_data": "x"}]):
            response = self.client.post(
                "/auth/group/", {"name": "g", "user_ids": [], "permissions_data": permissions_data}, format="json")
            self.assertEqual(response.status_code, 400, permissions_data)
        self.assertFalse(Group.objects.filter(name="g").exists())

    def test_valid_permissions_data_is_applied(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/auth/group/", {
            "name": "g", "user_ids": [],
            "permissions_data": [{"viewKey": "view_user", "hasView": True, "hasChange": False}],
        }, format="json")
        self.assertEqual(response.status_code, 201)
        group = Group.objects.get(name="g")
        self.assertTrue(group.permissions.filter(codename="view_user").exists())
