from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from coredata.models import City, PostalCode, Street, StreetNumber, StreetType
from service.models import Property


class GMAOPropertySearchViewTest(TestCase):
    """`GET /gmao/v1/properties/?search=` — cerca d'adreces de propietats
    actives per a la integració amb el GMAO, autenticada per token."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="gmao-client", password="not-used"
        )
        cls.token = Token.objects.create(user=cls.user)
        street_type = StreetType.objects.create(abbreviation="C", name="Carrer")
        city = City.objects.create(token="CITY-08001", name="Barcelona")
        postal_code = PostalCode.objects.create(code="08001")
        cls.street_major = Street.objects.create(
            name="Major", type=street_type, city=city
        )
        number = StreetNumber.objects.create(street=cls.street_major, number=123)
        cls.property = Property.objects.create(
            token="PR-001",
            name="Edifici Major",
            address_street=cls.street_major,
            address_street_number=number,
            address_postal_code=postal_code,
            address_city=city,
            is_active=True,
        )
        cls.other = Property.objects.create(
            token="PR-002",
            name="Casal Petit",
            cadastral="CAD-999",
            address_street=Street.objects.create(name="Petit"),
            address_postal_code=postal_code,
            address_city=city,
            is_active=True,
        )
        cls.inactive = Property.objects.create(
            token="PR-OFF",
            name="Major inactiva",
            address_street=cls.street_major,
            address_postal_code=postal_code,
            address_city=city,
            is_active=False,
        )
        street_type_cr = StreetType.objects.create(abbreviation="CR", name="")
        street_cr = Street.objects.create(
            name="Sant Miquel", type=street_type_cr, city=city
        )
        cls.cr_property = Property.objects.create(
            token="PR-CR",
            name="CR/SANT MIQUEL, 33",
            address_street=street_cr,
            address_street_number=StreetNumber.objects.create(
                street=street_cr, number=33
            ),
            address_postal_code=postal_code,
            address_city=city,
            is_active=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.url = reverse("gmao-inbound-properties")

    def _search(self, term, **params):
        return self.client.get(self.url, {"search": term, **params})

    def test_search_requires_authentication(self):
        anonymous = APIClient()
        response = anonymous.get(self.url, {"search": "Major"})
        self.assertEqual(response.status_code, 401)

    def test_search_rejects_invalid_token(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Token invalid-token")
        response = client.get(self.url, {"search": "Major"})
        self.assertEqual(response.status_code, 401)

    def test_search_by_street_name_returns_formatted_address(self):
        response = self._search("Major")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"],
            [
                {
                    "token": "PR-001",
                    "address": "C. Major, 123, 08001 Barcelona",
                    "street_type": "C",
                    "street_name": "Major",
                    "street_number": 123,
                    "postal_code": "08001",
                    "city": "Barcelona",
                }
            ],
        )

    def test_search_by_number_matches_exact_value(self):
        response = self._search("123")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["token"] for item in response.data["results"]], ["PR-001"]
        )

    def test_search_by_postal_code_returns_matching_properties(self):
        response = self._search("08001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["token"] for item in response.data["results"]],
            ["PR-001", "PR-002", "PR-CR"],
        )

    def test_search_ignores_trailing_dot_in_street_type(self):
        response = self._search("CR.")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"],
            [
                {
                    "token": "PR-CR",
                    "address": "CR. Sant Miquel, 33, 08001 Barcelona",
                    "street_type": "CR",
                    "street_name": "Sant Miquel",
                    "street_number": 33,
                    "postal_code": "08001",
                    "city": "Barcelona",
                }
            ],
        )

    def test_multi_term_search_matches_across_columns(self):
        response = self._search("CR. Sant 33")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["token"] for item in response.data["results"]], ["PR-CR"]
        )

    def test_search_matches_property_name_and_cadastral(self):
        self.assertEqual(
            [item["token"] for item in self._search("Casal").data["results"]],
            ["PR-002"],
        )
        self.assertEqual(
            [item["token"] for item in self._search("CAD-999").data["results"]],
            ["PR-002"],
        )

    def test_inactive_properties_are_excluded(self):
        self.assertNotIn(
            "PR-OFF",
            [item["token"] for item in self._search("Major").data["results"]],
        )

    def test_search_is_required(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Search is required"})

    def test_search_requires_at_least_three_characters(self):
        response = self._search("Ma")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"error": "Search must be at least 3 characters"},
        )

    def test_punctuation_only_search_returns_400(self):
        response = self._search("...")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data,
            {"error": "Search must contain at least one valid term"},
        )

    def test_results_use_pagination_envelope(self):
        response = self._search("08001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data),
            {"count", "page", "limit", "total_pages", "results"},
        )
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["limit"], 20)
        self.assertEqual(response.data["total_pages"], 1)

    def test_invalid_page_returns_400(self):
        response = self._search("08001", page=99)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Invalid page"})
