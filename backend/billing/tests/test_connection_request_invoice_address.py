"""Adreça i referència de les factures d'una sol·licitud d'escomesa."""
from django.test import TestCase

from billing.utils.connection_request_invoice import (
    format_location,
    get_connection_request_billing_address,
    get_connection_request_reference,
    get_connection_request_supply_address,
)
from coredata.models import (
    Address, City, Country, Person, PersonAddress, PostalCode, Province, Street, StreetNumber,
)
from service.models import Connection, ConnectionRequest


class ConnectionRequestInvoiceAddressTest(TestCase):
    def setUp(self):
        self.country = Country.objects.create(name='Espanya', iso_code='ES')
        self.province = Province.objects.create(name='Barcelona', country=self.country)
        self.city = City.objects.create(token='city-1', name='Municipi', province=self.province)
        self.postal_code = PostalCode.objects.create(code='08000', province=self.province, country=self.country)
        self.person = Person.objects.create(token='00000000T', name='Titular', surname='Prova')
        self.request = ConnectionRequest.objects.create(token='SOL-1', person=self.person)

    def _address(self, street_name, number):
        street = Street.objects.create(name=street_name, city=self.city)
        return Address.objects.create(
            street=street,
            street_number=StreetNumber.objects.create(street=street, number=number),
            postal_code='08000', city=self.city, province=self.province, country=self.country,
        )

    def _person_address(self, street_name, is_billing=True, is_active=True):
        return PersonAddress.objects.create(
            person=self.person, address=self._address(street_name, 1),
            is_billing=is_billing, is_active=is_active,
        )

    def _set_connection_location(self):
        street = Street.objects.create(name='Escomesa', city=self.city)
        self.request.address_street = street
        self.request.address_street_number = StreetNumber.objects.create(street=street, number=7)
        self.request.address_postal_code = self.postal_code
        self.request.address_city = self.city
        self.request.address_floor = '2'
        self.request.address_door = '1'
        self.request.save()

    def test_selected_billing_address_first(self):
        self._person_address('Notificacio')
        self.request.address_billing = self._person_address('Triada', is_billing=False)
        self.request.save()
        self._set_connection_location()

        fields = get_connection_request_billing_address(self.request)

        self.assertTrue(fields['address'].startswith('Triada, 1'))
        self.assertEqual(fields['country_iso'], 'ES')

    def test_person_active_billing_address_before_contact(self):
        self._person_address('Contacte', is_billing=False)
        self._person_address('Inactiva', is_billing=True, is_active=False)
        self._person_address('Facturacio', is_billing=True)

        fields = get_connection_request_billing_address(self.request)

        self.assertTrue(fields['address'].startswith('Facturacio, 1'))

    def test_falls_back_to_connection_location(self):
        self._person_address('Inactiva', is_active=False)
        self._set_connection_location()

        fields = get_connection_request_billing_address(self.request)

        self.assertEqual(fields['address'], 'Escomesa, 7 2-1')
        self.assertEqual(fields['postal_code'], '08000')
        self.assertEqual(format_location(fields), '08000 Municipi, Barcelona - Espanya')

    def test_no_address_at_all(self):
        self.assertIsNone(get_connection_request_billing_address(self.request))
        self.assertIsNone(get_connection_request_supply_address(self.request))

    def test_supply_address_is_connection_location(self):
        self.request.address_billing = self._person_address('Triada')
        self._set_connection_location()

        self.assertEqual(get_connection_request_supply_address(self.request), 'Escomesa, 7 2-1, Municipi')

    def test_reference_without_and_with_connection(self):
        self.assertEqual(get_connection_request_reference(self.request), ('connection_request', 'SOL-1'))

        self.request.connection = Connection.objects.create(token='ESC-1')
        self.request.save()

        self.assertEqual(get_connection_request_reference(self.request), ('connection', 'ESC-1'))
