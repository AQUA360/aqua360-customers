import base64

from django.template import Context, Template
from django.test import SimpleTestCase

from billing.templatetags.billing_filters import qr_base64

PREFIX = "data:image/png;base64,"


class QrBase64FilterTests(SimpleTestCase):
    def test_empty_values_return_empty_string(self):
        for value in (None, "", "   "):
            self.assertEqual(qr_base64(value), "")

    def test_returns_png_data_uri(self):
        result = qr_base64("123456")
        self.assertTrue(result.startswith(PREFIX))
        png = base64.b64decode(result[len(PREFIX):])
        self.assertTrue(png.startswith(b"\x89PNG"))

    def test_accepts_non_string_values(self):
        self.assertEqual(qr_base64(123456), qr_base64("123456"))

    def test_available_in_templates_without_load(self):
        rendered = Template("{{ token|qr_base64 }}").render(Context({"token": "ABC"}))
        self.assertTrue(rendered.startswith(PREFIX))
