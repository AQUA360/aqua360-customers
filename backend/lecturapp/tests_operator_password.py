"""Canvi de contrasenya des de l'app: la nova contrasenya ha de passar els validadors."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase

from lecturapp.models import ReadingOperator
from lecturapp.views import password_change

OLD_PASSWORD = "Rq7-vlm2Xp"


class OperatorPasswordChangeTestCase(TestCase):
    def setUp(self):
        self.operator = ReadingOperator.objects.create(name="Operari", surname="Prova", username="operari_2708")
        self.operator.set_password(OLD_PASSWORD)
        self.token = self.operator.generate_token().token

    def _change(self, new_password):
        request = RequestFactory().post("/lecturapp/auth/password-change/", {
            "old_password": OLD_PASSWORD, "new_password": new_password, "new_password_confirm": new_password,
        }, HTTP_X_APP_TOKEN=self.token)
        return password_change(request)

    def test_weak_password_is_rejected(self):
        for password in ("abc12", "abcdefgh", "12345678", "operari_27080"):
            with self.subTest(password=password):
                response = self._change(password)
                self.assertEqual(response.status_code, 400)
                self.assertIn(b"new_password", response.content)
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password(OLD_PASSWORD))

    def test_valid_password_is_changed(self):
        response = self._change("Zt8-kqw4Lm")
        self.assertEqual(response.status_code, 200)
        self.operator.refresh_from_db()
        self.assertTrue(self.operator.check_password("Zt8-kqw4Lm"))

    def test_createsuperoperator_rejects_weak_password(self):
        with self.assertRaises(CommandError):
            call_command("createsuperoperator", username="nou_2708", password="abc12", name="Nou", surname="Operari", stdout=StringIO())
        self.assertFalse(ReadingOperator.objects.filter(username="nou_2708").exists())
        call_command("createsuperoperator", username="nou_2708", password="Zt8-kqw4Lm", name="Nou", surname="Operari", stdout=StringIO())
        self.assertTrue(ReadingOperator.objects.get(username="nou_2708").check_password("Zt8-kqw4Lm"))
