from django.test import TestCase

from coredata.models import Address, City, Street, StreetNumber, StreetNumberType
from service.serializers.cluster_nozzle_serializer import ClusterNozzleSaveSerializer
from service.serializers.supply_point_serializer import SupplyPointSaveNozzleSerializer


class AddressExtraSerializerTests(TestCase):
    """Els serializers de la bateria busquen i creen l'adreça tenint en compte l'ampliació."""

    def setUp(self):
        self.city = City.objects.create(token='T1', name='Ciutat')
        self.street = Street.objects.create(name='Carrer Major')
        number_type = StreetNumberType.objects.get_or_create(type='N', defaults={'description': 'N'})[0]
        self.street_number = StreetNumber.objects.create(street=self.street, number_type=number_type, number=5)

    def _address_data(self, address_extra=None):
        return {
            'street': {'street_id': self.street.id, 'name': self.street.name, 'type': {'abbreviation': 'C', 'name': 'Carrer'}},
            'street_number': {'street_number_id': self.street_number.id, 'number_type': {'type': 'N'}, 'number': 5},
            'city': self.city.id,
            'postal_code': '', 'building': '', 'floor': '', 'door': '', 'stair': '',
            'address_extra': address_extra,
        }

    def _existing_address(self, address_extra):
        return Address.objects.create(street=self.street, street_number=self.street_number, city=self.city,
                                      postal_code='', building='', floor='', door='', stair='',
                                      address_extra=address_extra)

    def _creators(self):
        return [
            SupplyPointSaveNozzleSerializer()._create_address,
            ClusterNozzleSaveSerializer()._create_address_from_data,
        ]

    def test_ampliacions_diferents_creen_adreces_diferents(self):
        for create_address in self._creators():
            with self.subTest(create_address=create_address.__qualname__):
                bar = create_address(self._address_data('Bar'))
                shop = create_address(self._address_data('Botiga'))

                self.assertNotEqual(bar.id, shop.id)
                self.assertEqual(create_address(self._address_data('Bar')).id, bar.id)

    def test_ampliacio_es_desa_sense_espais(self):
        for create_address in self._creators():
            with self.subTest(create_address=create_address.__qualname__):
                Address.objects.all().delete()

                address = create_address(self._address_data('  Bar \n'))

                self.assertEqual(address.address_extra, 'Bar')

    def test_ampliacio_buida_reutilitza_adreces_null_i_buides(self):
        for create_address in self._creators():
            for stored in (None, '', '  '):
                with self.subTest(create_address=create_address.__qualname__, stored=stored):
                    Address.objects.all().delete()
                    existing = self._existing_address(stored)

                    self.assertEqual(create_address(self._address_data('')).id, existing.id)
                    self.assertEqual(create_address(self._address_data(None)).id, existing.id)
