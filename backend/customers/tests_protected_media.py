import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from coredata.models import AuthSessionToken


class ProtectedMediaViewTests(TestCase):
    """Només els logos de /media/ són públics; la resta exigeix un usuari actiu."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls.media_root)
        cls._override.enable()
        for relative in (
            'uploads/logo/1/logo.png',
            'uploads/exploitation/1/logo.jpg',
            'uploads/billing/readings/photos/reading.jpg',
            'uploads/blueprints/1/plan.pdf',
        ):
            path = os.path.join(cls.media_root, relative)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(b'x')

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='media-user', password='x')
        self.token = AuthSessionToken.create_for(self.user)

    def _get(self, path, **kwargs):
        return self.client.get(f'/media/{path}', **kwargs)

    def test_logos_publics(self):
        self.assertEqual(self._get('uploads/logo/1/logo.png').status_code, 200)
        self.assertEqual(self._get('uploads/exploitation/1/logo.jpg').status_code, 200)

    def test_imatges_fora_dels_logos_exigeixen_autenticacio(self):
        self.assertEqual(self._get('uploads/billing/readings/photos/reading.jpg').status_code, 403)

    def test_token_a_la_capcalera(self):
        response = self._get(
            'uploads/billing/readings/photos/reading.jpg',
            HTTP_AUTHORIZATION=f'Token {self.token.key}',
        )
        self.assertEqual(response.status_code, 200)

    def test_token_a_la_url_no_s_accepta(self):
        response = self._get(f'uploads/billing/readings/photos/reading.jpg?token={self.token.key}')
        self.assertEqual(response.status_code, 403)

    def test_usuari_inactiu(self):
        self.user.is_active = False
        self.user.save()
        response = self._get('uploads/blueprints/1/plan.pdf', HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.assertEqual(response.status_code, 403)

    def test_fitxer_inexistent_no_es_revela_sense_autenticacio(self):
        self.assertEqual(self._get('uploads/billing/readings/photos/no.jpg').status_code, 403)
        response = self._get('uploads/billing/readings/photos/no.jpg', HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.assertEqual(response.status_code, 404)

    def test_no_es_pot_sortir_de_media_root(self):
        self.assertEqual(self._get('uploads/logo/../../../etc/passwd').status_code, 404)
