from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token


class SearchResultsAuthTest(TestCase):
    """La cerca global no és accessible sense autenticar."""

    def test_anonymous_request_is_rejected(self):
        response = self.client.get("/search/results/", {"q": "a"})
        self.assertEqual(response.status_code, 401)

    def test_authenticated_request_is_allowed(self):
        user = User.objects.create_user("cerca", "cerca@example.com", "pwd")
        token = Token.objects.create(user=user)
        response = self.client.get(
            "/search/results/", {"q": "zzz-no-results"}, HTTP_AUTHORIZATION=f"Token {token.key}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
