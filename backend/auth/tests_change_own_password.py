"""Canvi de la contrasenya pròpia: qualsevol usuari autenticat, només la seva, i sense tancar la sessió actual."""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from coredata.models import AuthSessionToken

URL = reverse("change-own-password")
NEW_PASSWORD = "nova-clau-2026"


@override_settings(AUTH_TOKEN_NON_EXPIRING_USERS=[])
class ChangeOwnPasswordTests(TestCase):
    def setUp(self):
        # Login i canvi de contrasenya tenen límits a la memòria cau: cada test comença de zero
        cache.clear()
        self.addCleanup(cache.clear)
        # Usuari normal: sense rol d'administrador, ni grup, ni permisos
        self.user = User.objects.create_user("persona", "persona@example.com", "clau-antiga-1")
        self.other = User.objects.create_user("altra", "altra@example.com", "clau-altra-1")

    def login(self, username="persona", password="clau-antiga-1"):
        response = self.client.post(reverse("login"), {"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["token"]

    def change(self, key, data):
        return self.client.post(URL, data, content_type="application/json", HTTP_AUTHORIZATION=f"Token {key}")

    def test_usuari_sense_permisos_canvia_la_seva_contrasenya(self):
        key = self.login()
        response = self.change(key, {"current_password": "clau-antiga-1", "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_conserva_la_sessio_actual_i_tanca_les_altres(self):
        other_session = self.login()
        key = self.login()
        response = self.change(key, {"current_password": "clau-antiga-1", "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 204)
        self.assertTrue(AuthSessionToken.objects.filter(key=key).exists())
        self.assertFalse(AuthSessionToken.objects.filter(key=other_session).exists())

    def test_contrasenya_actual_incorrecta(self):
        key = self.login()
        response = self.change(key, {"current_password": "no-es-aquesta", "new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("clau-antiga-1"))

    def test_aplica_les_regles_de_contrasenya(self):
        key = self.login()
        response = self.change(key, {"current_password": "clau-antiga-1", "new_password": "curta"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json())

    def test_la_nova_ha_de_ser_diferent(self):
        key = self.login()
        response = self.change(key, {"current_password": "clau-antiga-1", "new_password": "clau-antiga-1"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json())

    def test_no_pot_canviar_la_d_un_altre_usuari(self):
        # Encara que s'enviï l'id o el nom d'un altre usuari, només es canvia la del que ha fet login
        key = self.login()
        response = self.change(key, {
            "id": self.other.pk,
            "username": "altra",
            "current_password": "clau-antiga-1",
            "new_password": NEW_PASSWORD,
        })
        self.assertEqual(response.status_code, 204)
        self.other.refresh_from_db()
        self.assertTrue(self.other.check_password("clau-altra-1"))

    def test_usuari_normal_no_pot_canviar_altres_des_de_la_gestio_d_usuaris(self):
        key = self.login()
        response = self.client.patch(
            reverse("user-detail", args=[self.other.pk]), {"new_pwd": NEW_PASSWORD},
            content_type="application/json", HTTP_AUTHORIZATION=f"Token {key}",
        )
        self.assertEqual(response.status_code, 403)
        self.other.refresh_from_db()
        self.assertTrue(self.other.check_password("clau-altra-1"))

    def test_cal_estar_autenticat(self):
        response = self.client.post(URL, {"current_password": "clau-antiga-1", "new_password": NEW_PASSWORD},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 401)


@override_settings(AUTH_TOKEN_NON_EXPIRING_USERS=[])
class OwnProfileTests(TestCase):
    """Fitxa pròpia: qualsevol usuari la veu i canvia nom, cognoms i correu; res més ni de ningú més."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("persona", "persona@example.com", "clau-antiga-1")
        self.other = User.objects.create_user("altra", "altra@example.com", "clau-altra-1")
        response = self.client.post(reverse("login"), {"username": "persona", "password": "clau-antiga-1"})
        self.auth = {"HTTP_AUTHORIZATION": f"Token {response.json()['token']}"}

    def patch(self, data):
        return self.client.patch(reverse("own-profile"), data, content_type="application/json", **self.auth)

    def test_consulta_la_fitxa_propia(self):
        response = self.client.get(reverse("own-profile"), **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "persona")
        self.assertEqual(response.json()["role"], "none")

    def test_canvia_nom_cognoms_i_correu(self):
        response = self.patch({"first_name": "Nom", "last_name": "Cognom", "email": "nou@example.com"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual((self.user.first_name, self.user.last_name, self.user.email),
                         ("Nom", "Cognom", "nou@example.com"))

    def test_no_canvia_nom_d_usuari_rol_ni_contrasenya(self):
        response = self.patch({"username": "customers", "role": "superuser", "is_superuser": True,
                               "is_staff": True, "password": "x", "new_pwd": "nova-clau-2026"})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "persona")
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)
        self.assertTrue(self.user.check_password("clau-antiga-1"))

    def test_correu_obligatori_i_valid(self):
        self.assertEqual(self.patch({"email": ""}).status_code, 400)
        self.assertEqual(self.patch({"email": "no-es-un-correu"}).status_code, 400)

    def test_no_toca_altres_usuaris(self):
        self.patch({"id": self.other.pk, "first_name": "Canviat"})
        self.other.refresh_from_db()
        self.assertEqual(self.other.first_name, "")
