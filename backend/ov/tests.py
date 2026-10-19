from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from coredata.models import ConfigProject, Person
from contract.models import Contract, ContractStatus

SLASH_TOKEN = "12345678/001"
PLAIN_TOKEN = "12345678"
HOLDER_TOKEN = "12345678Z"


class ContractOVViewTests(TestCase):
    """`GET /ov/contract-detail/` responde directamente (200), sense redirect.

    El token pot contenir barra (`/`), que una ruta `<str:token>` no pot
    resoldre: abans del fix això provocava `NoReverseMatch` (500).
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ov-contract-detail-test", password="not-used"
        )
        # `ContractFullDetailSerializer.get_termination_date` i el signal
        # `terminate_contract_update_bail` fan servir aquests paràmetres.
        for token, value in (
            ("contract_termination_completed_token", "3"),
            ("contract_terminated_status", "-1"),
        ):
            if not ConfigProject.objects.filter(token=token).exists():
                ConfigProject.objects.create(token=token, value=value)

        cls.status = ContractStatus.objects.create(token="1", name="Active")
        cls.holder = Person.objects.create(
            token=HOLDER_TOKEN, name="Test", surname="Holder"
        )
        cls.slash_contract = Contract.objects.create(
            token=SLASH_TOKEN, status=cls.status, holder=cls.holder
        )
        cls.plain_contract = Contract.objects.create(
            token=PLAIN_TOKEN, status=cls.status, holder=cls.holder
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_slash_token_returns_200_with_contract_data(self):
        response = self.client.get(
            reverse("contract-ov"), {"contract_token": SLASH_TOKEN}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))
        self.assertEqual(response.data["token"], SLASH_TOKEN)
        self.assertEqual(response.data["status_token"], "1")
        self.assertEqual(response.data["holder_token"], HOLDER_TOKEN)

    def test_plain_token_returns_200(self):
        response = self.client.get(
            reverse("contract-ov"), {"contract_token": PLAIN_TOKEN}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))
        self.assertEqual(response.data["token"], PLAIN_TOKEN)

    def test_unknown_token_returns_404_without_redirect(self):
        response = self.client.get(
            reverse("contract-ov"), {"contract_token": "99999999/999"}
        )

        self.assertEqual(response.status_code, 404)
        self.assertIsNone(response.get("Location"))
        self.assertEqual(response.data["error"], "Contract not found")

    def test_missing_contract_token_returns_400(self):
        response = self.client.get(reverse("contract-ov"))

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(response.get("Location"))
        self.assertEqual(
            response.data["error"], "Contract token is required"
        )

    def test_extra_query_params_are_processed_in_the_same_response(self):
        """El `dni` arriba al serialitzador (mateixa resposta, sense 302)."""
        response = self.client.get(
            reverse("contract-ov"),
            {"contract_token": SLASH_TOKEN, "dni": HOLDER_TOKEN},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))
        self.assertIn("is_account_holder", response.data)
        self.assertFalse(response.data["is_account_holder"])
