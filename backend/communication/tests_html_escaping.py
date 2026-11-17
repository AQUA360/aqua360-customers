"""Les dades de la persona no poden injectar HTML als correus i cartes, ni els PDF
de comunicacions carregar recursos locals o de la xarxa interna."""

import os
import socket
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase
from django.utils.safestring import mark_safe

from communication.utils.communication_service import _BLOCKED_PDF_RESOURCE, pdf_link_callback, refactor_text


class RefactorTextEscapingTests(SimpleTestCase):
    values = {'person.name': '<img src=x onerror=alert(1)>', 'person.address': 'Carrer A & B'}

    def test_values_are_escaped_for_html(self):
        text = refactor_text('Hola %person.name, %person.address', self.values, escape_values=True)
        self.assertNotIn('<img', text)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', text)
        self.assertIn('Carrer A &amp; B', text)

    def test_template_html_and_format_tags_are_kept(self):
        text = refactor_text('<p>**BOLD**%person.name**BOLD**</p>', self.values, escape_values=True)
        self.assertTrue(text.startswith('<p><b>&lt;img'))

    def test_safe_values_are_not_escaped(self):
        values = {'company.ov_url': mark_safe('<a href="https://ov.example.com">OV</a>')}
        text = refactor_text('%company.ov_url', values, escape_values=True)
        self.assertEqual(text, '<a href="https://ov.example.com">OV</a>')

    def test_plain_text_is_not_escaped_by_default(self):
        # Assumpte del correu i títol de la signatura: text pla
        self.assertEqual(refactor_text('%person.address', self.values), 'Carrer A & B')


def _resolve_to(address):
    return patch.object(socket, 'getaddrinfo', return_value=[(None, None, None, '', (address, 0))])


class PdfLinkCallbackTests(SimpleTestCase):
    def test_inline_data_is_allowed(self):
        uri = 'data:image/png;base64,AAAA'
        self.assertEqual(pdf_link_callback(uri, None), uri)

    def test_application_and_media_files_are_allowed(self):
        font = os.path.join(settings.BASE_DIR, 'config', 'fonts', 'font.ttf')
        logo = os.path.join(settings.MEDIA_ROOT, 'uploads', 'logo.png')
        self.assertEqual(pdf_link_callback(font, None), font)
        self.assertEqual(pdf_link_callback(logo, None), logo)
        self.assertEqual(pdf_link_callback(f'file://{logo}', None), logo)

    def test_files_outside_the_application_are_blocked(self):
        for uri in ('/etc/passwd', 'file:///etc/passwd', os.path.join(settings.BASE_DIR, '..', '..', 'etc', 'passwd')):
            with self.subTest(uri=uri):
                self.assertEqual(pdf_link_callback(uri, None), _BLOCKED_PDF_RESOURCE)

    def test_internal_network_is_blocked(self):
        for address in ('127.0.0.1', '10.0.0.5', '192.168.1.10', '169.254.169.254', '::1'):
            with self.subTest(address=address), _resolve_to(address):
                self.assertEqual(pdf_link_callback('http://intern.example/x.png', None), _BLOCKED_PDF_RESOURCE)

    def test_public_urls_are_allowed(self):
        with _resolve_to('93.184.216.34'):
            uri = 'https://images.example.com/logo.png'
            self.assertEqual(pdf_link_callback(uri, None), uri)

    def test_media_domain_is_allowed_even_if_internal(self):
        with self.settings(DOMAIN_MEDIA='http://backend:8000/'), _resolve_to('172.18.0.3'):
            uri = 'http://backend:8000/media/uploads/logo.png'
            self.assertEqual(pdf_link_callback(uri, None), uri)

    def test_unresolvable_hosts_and_other_schemes_are_blocked(self):
        with patch.object(socket, 'getaddrinfo', side_effect=socket.gaierror):
            self.assertEqual(pdf_link_callback('https://no-existeix.invalid/x.png', None), _BLOCKED_PDF_RESOURCE)
        self.assertEqual(pdf_link_callback('ftp://example.com/x.png', None), _BLOCKED_PDF_RESOURCE)
