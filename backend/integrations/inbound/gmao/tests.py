from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token

from service.models import Property

from .permissions import GMAO_GROUP


class GMAOLoginTest(TestCase):
    """El GMAO obté el token amb el seu propi login, limitat al grup `gmao`."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.url = reverse("gmao-inbound-login")
        group = Group.objects.create(name=GMAO_GROUP)
        self.gmao_user = User.objects.create_user(username="gmao", password="secret")
        self.gmao_user.groups.add(group)
        self.other_user = User.objects.create_user(username="altre", password="secret")

    def _login(self, username, password):
        return self.client.post(self.url, {"username": username, "password": password})

    def test_gmao_user_gets_token(self):
        resp = self._login("gmao", "secret")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["username"], "gmao")
        self.assertEqual(resp.json()["token"], Token.objects.get(user=self.gmao_user).key)

    def test_same_token_on_repeated_login(self):
        first = self._login("gmao", "secret").json()["token"]
        second = self._login("gmao", "secret").json()["token"]
        self.assertEqual(first, second)

    def test_wrong_password_rejected(self):
        resp = self._login("gmao", "incorrecta")
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn("token", resp.json())

    def test_user_outside_group_gets_same_error_as_bad_credentials(self):
        bad_password = self._login("gmao", "incorrecta")
        outside = self._login("altre", "secret")
        self.assertEqual(outside.status_code, 400)
        self.assertEqual(outside.json(), bad_password.json())
        self.assertFalse(Token.objects.filter(user=self.other_user).exists())

    def test_superuser_outside_group_rejected(self):
        User.objects.create_superuser(username="admin", password="secret")
        self.assertEqual(self._login("admin", "secret").status_code, 400)

    def test_user_locked_after_failed_attempts(self):
        from django.conf import settings

        for _ in range(settings.AXES_FAILURE_LIMIT):
            self._login("gmao", "incorrecta")
        self.assertEqual(self._login("gmao", "secret").status_code, 429)

    def test_general_login_still_works_for_any_user(self):
        resp = self.client.post(reverse("login"), {"username": "altre", "password": "secret"})
        self.assertEqual(resp.status_code, 200)


class GMAOPropertySearchAccessTest(TestCase):
    """La cerca d'immobles només és per a usuaris del grup `gmao`."""

    def setUp(self):
        self.url = reverse("gmao-inbound-properties")
        group = Group.objects.create(name=GMAO_GROUP)
        self.gmao_user = User.objects.create_user(username="gmao", password="secret")
        self.gmao_user.groups.add(group)
        self.gmao_token = Token.objects.create(user=self.gmao_user)
        self.other_token = Token.objects.create(
            user=User.objects.create_user(username="altre", password="secret")
        )
        Property.objects.create(token="P1", name="Finca Prova", is_active=True)

    def _get(self, token, path=None, **params):
        return self.client.get(
            path or self.url, params, HTTP_AUTHORIZATION=f"Token {token.key}"
        )

    def test_anonymous_rejected(self):
        self.assertEqual(self.client.get(self.url, {"search": "Finca"}).status_code, 401)

    def test_gmao_user_can_search(self):
        resp = self._get(self.gmao_token, search="Finca")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_user_outside_group_forbidden(self):
        self.assertEqual(self._get(self.other_token, search="Finca").status_code, 403)

    def test_gmao_token_cannot_reach_other_apis(self):
        resp = self._get(self.gmao_token, path="/auth/user/")
        self.assertEqual(resp.status_code, 403)

    def test_login_then_search(self):
        token = self.client.post(
            reverse("gmao-inbound-login"), {"username": "gmao", "password": "secret"}
        ).json()["token"]
        resp = self.client.get(
            self.url, {"search": "Finca"}, HTTP_AUTHORIZATION=f"Token {token}"
        )
        self.assertEqual(resp.status_code, 200)
