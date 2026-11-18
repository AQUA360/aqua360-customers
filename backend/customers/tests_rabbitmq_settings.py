from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from customers.settings import _resolve_rabbitmq_url


class ResolveRabbitmqUrlTests(SimpleTestCase):
    """Amb RabbitMQ activat cal RABBITMQ_URL, i amb DEBUG=False sense credencials conegudes."""

    def test_desactivat_no_cal_url(self):
        for debug in (True, False):
            with self.subTest(debug=debug):
                self.assertEqual(_resolve_rabbitmq_url("", enabled=False, debug=debug), "")

    def test_activat_sense_url_falla(self):
        for url in (None, "", "   "):
            for debug in (True, False):
                with self.subTest(url=url, debug=debug), self.assertRaises(ImproperlyConfigured):
                    _resolve_rabbitmq_url(url, enabled=True, debug=debug)

    def test_credencials_conegudes_fallen_sense_debug(self):
        for url in (
            "amqp://guest:guest@localhost:5672//",
            "amqps://guest:guest@broker.example:5671/vhost",
            "amqp://user:password@localhost:5672//",
            "amqps://broker.example:5671/vhost",
            "amqp://gu%65st:guest@localhost/",
        ):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured) as error:
                _resolve_rabbitmq_url(url, enabled=True, debug=False)
            self.assertNotIn(url, str(error.exception))

    def test_credencials_conegudes_es_toleren_amb_debug(self):
        url = "amqp://guest:guest@localhost:5672//"
        self.assertEqual(_resolve_rabbitmq_url(url, enabled=True, debug=True), url)

    def test_credencials_propies(self):
        url = "amqps://instal-lacio:Xk29%40pQz@broker.example:5671/vhost"
        self.assertEqual(_resolve_rabbitmq_url(f"  {url} ", enabled=True, debug=False), url)

    def test_url_invalida(self):
        with self.assertRaises(ImproperlyConfigured):
            _resolve_rabbitmq_url("amqp://u:p@[host/", enabled=True, debug=False)
