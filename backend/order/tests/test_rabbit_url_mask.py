from django.test import SimpleTestCase

from order.services.rabbit import mask_url_password


class MaskUrlPasswordTests(SimpleTestCase):
    """La contrasenya de RABBITMQ_URL no pot arribar als registres."""

    def test_amaga_la_contrasenya(self):
        cases = (
            ("amqps://usuari:secret@broker.example:5671/vhost", "amqps://usuari:***@broker.example:5671/vhost"),
            ("amqp://guest:guest@localhost:5672//", "amqp://guest:***@localhost:5672//"),
            ("amqp://usuari:p%40ss%3Aw@host/", "amqp://usuari:***@host/"),
            ("amqp://usuari:a@b@host:5672/", "amqp://usuari:***@host:5672/"),
            ("amqp://usuari:@host/", "amqp://usuari:***@host/"),
        )
        for url, expected in cases:
            with self.subTest(url=url):
                masked = mask_url_password(url)
                self.assertEqual(masked, expected)

    def test_sense_contrasenya_no_canvia(self):
        for url in ("amqp://localhost:5672/", "amqp://usuari@host/", "", None):
            with self.subTest(url=url):
                self.assertEqual(mask_url_password(url), url or "")
