"""
Les contrasenyes dels operaris de l'app (usuari de l'app d'un operari) passen els mateixos
validadors que els usuaris de l'API: validadors de Django, mínim 8 caràcters i un número.
"""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from lecturapp.models import ReadingOperator
from order.models import Operator
from order.views.operator_view import OperatorViewSet

WEAK_PASSWORDS = ("abc12", "abcdefgh", "12345678", "password1")
VALID_PASSWORD = "Rq7-vlm2Xp"


class OperatorPasswordTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin-2708", "admin-2708@example.com", "x")
        cls.factory = APIRequestFactory()

    def _create(self, password, password_confirm=None, username="operari_2708"):
        request = self.factory.post("/operator/", {
            "token": "2708-OP", "name": "Operari", "surname": "Prova",
            "app_user": {
                "name": "Operari", "surname": "Prova", "username": username,
                "password": password, "password_confirm": password if password_confirm is None else password_confirm,
            },
        }, format="json")
        force_authenticate(request, user=self.admin)
        return OperatorViewSet.as_view({"post": "create"})(request)

    def _update(self, operator, app_user):
        request = self.factory.patch(f"/operator/{operator.pk}/", {"app_user": app_user}, format="json")
        force_authenticate(request, user=self.admin)
        return OperatorViewSet.as_view({"patch": "partial_update"})(request, pk=operator.pk)

    def _operator_with_app_user(self):
        app_user = ReadingOperator.objects.create(name="Operari", surname="Prova", username="operari_2708")
        app_user.set_password(VALID_PASSWORD)
        return Operator.objects.create(token="2708-OP", name="Operari", surname="Prova", app_user=app_user)

    def test_create_with_weak_password_returns_field_error(self):
        for password in WEAK_PASSWORDS:
            with self.subTest(password=password):
                response = self._create(password)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.data["app_user"]["password"])
        self.assertFalse(Operator.objects.exists())
        self.assertFalse(ReadingOperator.objects.exists())

    def test_create_with_password_similar_to_username_fails(self):
        response = self._create("operari_27080", username="operari_2708")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data["app_user"])

    def test_create_with_valid_password(self):
        response = self._create(VALID_PASSWORD)
        self.assertEqual(response.status_code, 201, response.data)
        app_user = ReadingOperator.objects.get(username="operari_2708")
        self.assertTrue(app_user.check_password(VALID_PASSWORD))

    def test_create_with_mismatched_passwords(self):
        response = self._create(VALID_PASSWORD, password_confirm=VALID_PASSWORD + "x")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data["app_user"])

    def test_change_password_weak_is_rejected(self):
        operator = self._operator_with_app_user()
        for password in WEAK_PASSWORDS:
            with self.subTest(password=password):
                response = self._update(operator, {
                    "username": "operari_2708", "name": "Operari", "surname": "Prova",
                    "password": password, "password_confirm": password,
                })
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.data["app_user"]["password"])
        operator.app_user.refresh_from_db()
        self.assertTrue(operator.app_user.check_password(VALID_PASSWORD))

    def test_change_password_valid(self):
        operator = self._operator_with_app_user()
        new_password = "Zt8-kqw4Lm"
        response = self._update(operator, {
            "username": "operari_2708", "name": "Operari", "surname": "Prova",
            "password": new_password, "password_confirm": new_password,
        })
        self.assertEqual(response.status_code, 200, response.data)
        operator.app_user.refresh_from_db()
        self.assertTrue(operator.app_user.check_password(new_password))

    def test_update_without_password_keeps_existing_one(self):
        # Els operaris amb contrasenyes antigues es poden continuar editant sense canviar-la
        operator = self._operator_with_app_user()
        operator.app_user.set_password("abc123")
        response = self._update(operator, {"username": "operari_2708", "name": "Operari", "surname": "Nou"})
        self.assertEqual(response.status_code, 200, response.data)
        operator.app_user.refresh_from_db()
        self.assertEqual(operator.app_user.surname, "Nou")
        self.assertTrue(operator.app_user.check_password("abc123"))
