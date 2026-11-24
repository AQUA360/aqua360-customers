"""Tokens d'accés: caducitat, logout, revocació en canviar la contrasenya i integracions."""
import os
import shutil
import tempfile
from datetime import timedelta

from django.core.cache import cache
from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

from auth.serializers import UserSerializer
from customers.views import protected_media_view
from coredata.authentication import get_user_from_token_key
from coredata.models import AuthSessionToken

PROTECTED_URL = "/auth/permission/my-permissions/"


@override_settings(AUTH_TOKEN_IDLE_HOURS=24, AUTH_TOKEN_MAX_AGE_DAYS=7, AUTH_TOKEN_NON_EXPIRING_USERS=[])
class AuthTokenTests(TestCase):
    def setUp(self):
        # El login té un límit d'intents per IP a la memòria cau: cada test comença de zero.
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("persona", "persona@example.com", "pwd-antiga")

    def login(self, username="persona", password="pwd-antiga"):
        response = self.client.post(reverse("login"), {"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["token"]

    def get(self, key, url=PROTECTED_URL):
        return self.client.get(url, HTTP_AUTHORIZATION=f"Token {key}")

    def test_login_crea_un_token_de_sessio_per_login(self):
        key1 = self.login()
        key2 = self.login()
        self.assertNotEqual(key1, key2)
        self.assertEqual(AuthSessionToken.objects.filter(user=self.user).count(), 2)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        self.assertEqual(self.get(key1).status_code, 200)
        self.assertEqual(self.get(key2).status_code, 200)

    def test_caduca_per_inactivitat(self):
        key = self.login()
        AuthSessionToken.objects.filter(key=key).update(last_used=timezone.now() - timedelta(hours=25))
        self.assertEqual(self.get(key).status_code, 401)
        self.assertFalse(AuthSessionToken.objects.filter(key=key).exists())

    def test_activitat_recent_allarga_la_sessio(self):
        key = self.login()
        AuthSessionToken.objects.filter(key=key).update(last_used=timezone.now() - timedelta(hours=23))
        self.assertEqual(self.get(key).status_code, 200)
        last_used = AuthSessionToken.objects.get(key=key).last_used
        self.assertGreater(last_used, timezone.now() - timedelta(minutes=1))

    def test_caduca_per_antiguitat_encara_que_hi_hagi_activitat(self):
        key = self.login()
        AuthSessionToken.objects.filter(key=key).update(
            created=timezone.now() - timedelta(days=8), last_used=timezone.now()
        )
        self.assertEqual(self.get(key).status_code, 401)

    def test_logout_nomes_tanca_la_sessio_actual(self):
        key1 = self.login()
        key2 = self.login()
        response = self.client.post(reverse("logout"), HTTP_AUTHORIZATION=f"Token {key1}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.get(key1).status_code, 401)
        self.assertEqual(self.get(key2).status_code, 200)

    def test_logout_sense_token_retorna_401(self):
        self.assertEqual(self.client.post(reverse("logout")).status_code, 401)

    def test_canvi_de_contrasenya_revoca_totes_les_sessions(self):
        key1 = self.login()
        key2 = self.login()
        self.user.set_password("pwd-nova")
        self.user.save()
        self.assertEqual(self.get(key1).status_code, 401)
        self.assertEqual(self.get(key2).status_code, 401)

    def test_desar_sense_canviar_la_contrasenya_no_revoca(self):
        key = self.login()
        self.user.first_name = "Nom"
        self.user.save()
        self.assertEqual(self.get(key).status_code, 200)

    def test_canvi_de_contrasenya_des_del_serializer_d_usuaris(self):
        admin = User.objects.create_superuser("customers", "customers@example.com", "pwd-admin")
        admin_key = self.login("customers", "pwd-admin")
        key = self.login()
        request = RequestFactory().patch("/")
        request.user = admin
        serializer = UserSerializer(
            self.user, data={"new_pwd": "Pwd-nova-1234"}, partial=True, context={"request": request}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.assertEqual(self.get(key).status_code, 401)
        self.assertEqual(self.get(admin_key).status_code, 200)

    def test_usuari_inactiu_es_rebutjat(self):
        key = self.login()
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.get(key).status_code, 401)

    def test_token_permanent_de_persona_ja_no_serveix(self):
        token = Token.objects.create(user=self.user)
        self.assertEqual(self.get(token.key).status_code, 401)

    def test_login_esborra_les_sessions_caducades(self):
        old_key = self.login()
        AuthSessionToken.objects.filter(key=old_key).update(last_used=timezone.now() - timedelta(days=2))
        self.login()
        self.assertFalse(AuthSessionToken.objects.filter(key=old_key).exists())


@override_settings(AUTH_TOKEN_NON_EXPIRING_USERS=["integracio"])
class IntegrationTokenTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_usuari_per_nom_conserva_el_token_permanent(self):
        user = User.objects.create_user("integracio", "i@example.com", "pwd")
        response = self.client.post(reverse("login"), {"username": "integracio", "password": "pwd"})
        key = response.json()["token"]
        self.assertEqual(key, Token.objects.get(user=user).key)
        self.assertFalse(AuthSessionToken.objects.filter(user=user).exists())
        self.assertEqual(
            self.client.get(PROTECTED_URL, HTTP_AUTHORIZATION=f"Token {key}").status_code, 200
        )

    def test_usuari_per_grup_conserva_el_token_permanent(self):
        user = User.objects.create_user("ovuser", "ov@example.com", "pwd")
        user.groups.add(Group.objects.create(name="ov"))
        token = Token.objects.create(user=user)
        self.assertEqual(get_user_from_token_key(token.key), user)

    def test_canvi_de_contrasenya_tambe_revoca_el_token_d_integracio(self):
        user = User.objects.create_user("integracio", "i@example.com", "pwd")
        token = Token.objects.create(user=user)
        user.set_password("pwd-nova")
        user.save()
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())


class ProtectedMediaTokenTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media_root)
        with open(os.path.join(self.media_root, "doc.pdf"), "wb") as fh:
            fh.write(b"%PDF-1.4")
        self.user = User.objects.create_user("persona", "persona@example.com", "pwd")

    def get_media(self, key):
        # Es crida la vista directament: el FileResponse del client de proves
        # tanca la connexió a la BD en acabar.
        request = RequestFactory().get("/media/doc.pdf", HTTP_AUTHORIZATION=f"Token {key}")
        request.user = AnonymousUser()
        with override_settings(MEDIA_ROOT=self.media_root):
            response = protected_media_view(request, "doc.pdf")
        if hasattr(response, "file_to_stream"):
            response.file_to_stream.close()
        return response.status_code

    def test_fitxer_protegit_amb_token_valid_i_caducat(self):
        session = AuthSessionToken.create_for(self.user)
        self.assertEqual(self.get_media(session.key), 200)
        AuthSessionToken.objects.filter(pk=session.pk).update(last_used=timezone.now() - timedelta(days=2))
        self.assertEqual(self.get_media(session.key), 403)

    def test_fitxer_protegit_amb_token_permanent_de_persona(self):
        token = Token.objects.create(user=self.user)
        self.assertEqual(self.get_media(token.key), 403)
