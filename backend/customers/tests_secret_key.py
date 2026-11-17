from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from customers.settings import DEV_SECRET_KEY, INSECURE_SECRET_KEYS, _resolve_secret_key


class ResolveSecretKeyTests(SimpleTestCase):
    """L'arrencada ha de fallar sense una SECRET_KEY segura quan DEBUG=False."""

    def test_sense_debug_i_sense_clau_falla(self):
        for value in (None, "", "   "):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                _resolve_secret_key(value, debug=False)

    def test_sense_debug_amb_clau_coneguda_falla(self):
        for value in INSECURE_SECRET_KEYS:
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                _resolve_secret_key(value, debug=False)

    def test_sense_debug_amb_clau_propia_la_retorna(self):
        self.assertEqual(_resolve_secret_key("una-clau-propia-i-aleatoria", debug=False), "una-clau-propia-i-aleatoria")

    def test_amb_debug_i_sense_clau_fa_servir_la_de_desenvolupament(self):
        self.assertEqual(_resolve_secret_key("", debug=True), DEV_SECRET_KEY)

    def test_amb_debug_i_clau_propia_la_retorna(self):
        self.assertEqual(_resolve_secret_key("una-clau-propia", debug=True), "una-clau-propia")
