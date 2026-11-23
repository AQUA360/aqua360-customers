from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from coredata.models import AuthSessionToken

from coredata.models import Person


class SearchResultsAuthTest(TestCase):
    """La cerca global no és accessible sense autenticar."""

    def test_anonymous_request_is_rejected(self):
        response = self.client.get("/search/results/", {"q": "a"})
        self.assertEqual(response.status_code, 401)

    def test_authenticated_request_is_allowed(self):
        user = User.objects.create_user("cerca", "cerca@example.com", "pwd")
        token = AuthSessionToken.create_for(user)
        response = self.client.get(
            "/search/results/", {"q": "zzz-no-results"}, HTTP_AUTHORIZATION=f"Token {token.key}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])


class SearchResultsSecurityAndPagingTest(TestCase):
    """Permisos view_*, validació de paginació i límit de page_size."""

    def setUp(self):
        self.user = User.objects.create_user("cerca-limited", "limited@example.com", "pwd")
        self.token = Token.objects.create(user=self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}
        Person.objects.create(token="PER-SECRET", name="Secret", surname="Person")

    def _auth_get(self, params):
        return self.client.get("/search/results/", params, **self.auth)

    def test_without_view_permission_hides_model_results(self):
        response = self._auth_get({"q": "Secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.assertEqual(response.json()["total_count"], 0)

    def test_with_view_person_returns_matching_person(self):
        ct = ContentType.objects.get_for_model(Person)
        perm = Permission.objects.get(content_type=ct, codename="view_person")
        self.user.user_permissions.add(perm)
        # Evita cache de permisos de l'instància d'usuari
        self.user = User.objects.get(pk=self.user.pk)

        response = self._auth_get({"q": "Secret"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["entity"], "Person")
        self.assertEqual(data["results"][0]["item_id"], Person.objects.get(token="PER-SECRET").id)

    def test_invalid_page_returns_400(self):
        response = self._auth_get({"q": "x", "page": "abc"})
        self.assertEqual(response.status_code, 400)

    def test_invalid_page_size_returns_400(self):
        response = self._auth_get({"q": "x", "page_size": "nope"})
        self.assertEqual(response.status_code, 400)

    def test_page_size_is_capped(self):
        response = self._auth_get({"q": "zzz-no-results", "page_size": "500"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page_size"], 100)

    def test_matching_entities_ignores_entity_filter(self):
        """Els chips de filtre han de reflectir totes les entitats amb match, no només la filtrada."""
        ct = ContentType.objects.get_for_model(Person)
        perm = Permission.objects.get(content_type=ct, codename="view_person")
        self.user.user_permissions.add(perm)
        self.user = User.objects.get(pk=self.user.pk)

        response = self._auth_get({"q": "Secret", "entity": "Person"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["results"][0]["entity"], "Person")
        self.assertIn("Person", data["matching_entities"])
