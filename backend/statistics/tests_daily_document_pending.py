"""Comptador de documents diaris del menú: sense permís d'estadístiques torna zeros, no un 403."""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient


class DailyDocumentPendingTests(TestCase):
    URL = "/statistics/daily-document/pending/"

    def test_usuari_sense_permisos_rep_zeros(self):
        user = User.objects.create_user("persona", "persona@example.com", "clau-1234")
        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"pending": 0, "errors": 0})

    def test_cal_estar_autenticat(self):
        self.assertEqual(APIClient().get(self.URL).status_code, 401)
