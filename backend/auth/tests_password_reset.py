"""Recuperació de la contrasenya des del login: quan s'envia el correu i com es desa la nova."""
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from coredata.models import AuthSessionToken
from service.models import Company, CompanyConfig, CompanyConfigEmail

REQUEST_URL = reverse("password-reset")
CONFIRM_URL = reverse("password-reset-confirm")
SEND = "auth.password_reset_service._send"
APP_URL = "https://app.example.test"


@override_settings(
    FRONTEND_URL=APP_URL,
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    AUTH_TOKEN_NON_EXPIRING_USERS=[],
    AUTH_TOKEN_NON_EXPIRING_GROUPS=[],
)
class PasswordResetRequestTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("persona", "persona@example.com", "clau-antiga-1")
        config = CompanyConfig.objects.create(mail_send_smtp_server="smtp.example.test", mail_send_smtp_port=587)
        CompanyConfigEmail.objects.create(company_config=config, mail_send_mail="envia@example.test", is_default=True)
        self.company = Company.objects.create(name="Empresa", config=config, is_default=True)

    def ask(self, username="persona", **extra):
        return self.client.post(REQUEST_URL, {"username": username}, content_type="application/json", **extra)

    def test_envia_el_correu_amb_l_enllac(self):
        with mock.patch(SEND) as send:
            response = self.ask()
        self.assertEqual(response.json(), {"status": "sent"})
        send.assert_called_once()
        link = send.call_args.args[3]
        self.assertTrue(link.startswith(f"{APP_URL}/auth/reset-password?uid="))
        self.assertIn("token=", link)

    def test_usuari_inexistent(self):
        with mock.patch(SEND) as send:
            self.assertEqual(self.ask("no-existeix").json(), {"status": "unavailable"})
        send.assert_not_called()

    def test_usuari_sense_correu(self):
        self.user.email = ""
        self.user.save()
        with mock.patch(SEND) as send:
            self.assertEqual(self.ask().json(), {"status": "unavailable"})
        send.assert_not_called()

    def test_usuari_inactiu(self):
        self.user.is_active = False
        self.user.save()
        with mock.patch(SEND) as send:
            self.assertEqual(self.ask().json(), {"status": "unavailable"})
        send.assert_not_called()

    def test_empresa_sense_correu_configurat(self):
        CompanyConfigEmail.objects.all().update(is_active=False)
        with mock.patch(SEND) as send:
            self.assertEqual(self.ask().json(), {"status": "unavailable"})
        send.assert_not_called()

    def test_empresa_sense_servidor_smtp(self):
        CompanyConfig.objects.all().update(mail_send_smtp_server=None)
        with mock.patch(SEND) as send:
            self.assertEqual(self.ask().json(), {"status": "unavailable"})
        send.assert_not_called()

    def test_error_en_enviar(self):
        with mock.patch(SEND, side_effect=OSError("smtp")):
            self.assertEqual(self.ask().json(), {"status": "unavailable"})

    @override_settings(FRONTEND_URL="", CSRF_TRUSTED_ORIGINS=["https://app.example.test"])
    def test_origin_de_confianca(self):
        with mock.patch(SEND) as send:
            self.assertEqual(self.ask(HTTP_ORIGIN="https://app.example.test").json(), {"status": "sent"})
        self.assertTrue(send.call_args.args[3].startswith("https://app.example.test/auth/reset-password?"))

    @override_settings(FRONTEND_URL="", CSRF_TRUSTED_ORIGINS=["https://app.example.test"])
    def test_origin_no_de_confianca_no_envia(self):
        # Un enllaç amb el token cap a un altre domini permetria prendre el compte
        with mock.patch(SEND) as send:
            self.assertEqual(self.ask(HTTP_ORIGIN="https://atacant.example").json(), {"status": "unavailable"})
        send.assert_not_called()


@override_settings(AUTH_TOKEN_NON_EXPIRING_USERS=[], AUTH_TOKEN_NON_EXPIRING_GROUPS=[])
class PasswordResetConfirmTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user("persona", "persona@example.com", "clau-antiga-1")
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)

    def confirm(self, **data):
        payload = {"uid": self.uid, "token": self.token, **data}
        return self.client.post(CONFIRM_URL, payload, content_type="application/json")

    def test_comprova_l_enllac(self):
        self.assertEqual(self.confirm().json(), {"valid": True, "strict_rules": False})
        self.assertEqual(self.confirm(token="dolent").json()["valid"], False)

    def test_desa_la_contrasenya_i_tanca_les_sessions(self):
        session = AuthSessionToken.create_for(self.user)
        response = self.confirm(new_password="nova-clau-2026")
        self.assertEqual(response.status_code, 204)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("nova-clau-2026"))
        self.assertFalse(AuthSessionToken.objects.filter(pk=session.pk).exists())

    def test_l_enllac_nomes_val_una_vegada(self):
        self.assertEqual(self.confirm(new_password="nova-clau-2026").status_code, 204)
        response = self.confirm(new_password="una-altra-2026")
        self.assertEqual(response.status_code, 400)
        self.assertIn("token", response.json())

    def test_aplica_les_regles(self):
        response = self.confirm(new_password="curta")
        self.assertEqual(response.status_code, 400)
        self.assertIn("new_password", response.json())
