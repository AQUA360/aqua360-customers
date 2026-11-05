from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from coredata.models import Address, City, Street, StreetNumber, StreetNumberType, StreetType
from logger.models import LogSupplyPointChange
from service.models import (
    Cluster, ClusterNozzle, ClusterNozzleStatus, ClusterNozzleType, Property, SupplyPoint, SupplyPointPlacement, SupplyPointStatus,
)
from service.serializers.supply_point_serializer import SupplyPointSerializer


class SupplyPointAddressDictTests(TestCase):
    """El formulari ràpid (alta i bateria) envia l'adreça com a dict a `address`, no a `address_data`."""

    def setUp(self):
        request = APIRequestFactory().post('/', HTTP_HOST='localhost')
        request.user = User.objects.create(username='tester')
        self.context = {'request': request}

        SupplyPointStatus.objects.create(token='ACTIVE', name='Actiu', is_default=True)
        ClusterNozzleStatus.objects.create(token='OK', name='OK', is_default=True)
        ClusterNozzleType.objects.create(token='STD', name='Estàndard', is_default=True)
        self.portella = SupplyPointPlacement.objects.create(token='PORTELLA', name='Portella')
        self.bateria = SupplyPointPlacement.objects.create(token='BATERIA', name='Bateria')

        self.city = City.objects.create(token='T1', name='Ciutat')
        street_type = StreetType.objects.create(abbreviation='C', name='Carrer', aca_abbreviation='CR')
        self.street = Street.objects.create(name='Carrer Major', type=street_type, name_2='', city=self.city)
        number_type = StreetNumberType.objects.get_or_create(type='N', defaults={'description': 'N'})[0]
        self.street_number = StreetNumber.objects.create(
            street=self.street, number_type=number_type, number=10, number_suffix='', number_end_suffix='',
        )
        self.property = Property.objects.create(token='P1', name='Finca')

        self.address = Address.objects.create(
            street=self.street, street_number=self.street_number, city=self.city,
            stair='B', floor='BX', door='2', address_extra='PORTELLA',
        )
        self.cluster = Cluster.objects.create(token='B1', nb_nozzles=1)
        self.nozzle = ClusterNozzle.objects.create(cluster=self.cluster, token='B1/1', position=1, col=1)
        self.supply_point = SupplyPoint.objects.create(
            token='SP1', address=self.address, property=self.property,
            placement=self.portella, cluster_nozzle=self.nozzle,
        )

    def _payload(self, address_extra):
        return {
            'token': 'SP1',
            'placement_id': self.bateria.id,
            'property_id': self.property.id,
            'cluster_id': self.cluster.id,
            'is_active': True,
            'address': {
                'stair': 'B', 'floor': 'BX', 'door': '2', 'building': None,
                'address_extra': address_extra,
                'street': {'id': self.street.id, 'street_id': self.street.id, 'name': self.street.name,
                           'type_abbreviation': 'C', 'type_name': 'Carrer'},
                'street_number': {'id': self.street_number.id, 'street_number_id': self.street_number.id,
                                  'number': 10, 'number_type_type': 'N'},
                'city': self.city.id,
            },
        }

    def test_editar_des_de_la_bateria_actualitza_el_mateix_punt(self):
        serializer = SupplyPointSerializer(
            self.supply_point, data=self._payload('BATERIA'), context=self.context, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        updated.refresh_from_db()

        self.assertEqual(updated.id, self.supply_point.id)
        self.assertEqual(updated.placement, self.bateria)
        self.assertEqual(updated.cluster_nozzle, self.nozzle)
        self.assertEqual(ClusterNozzle.objects.filter(cluster=self.cluster).count(), 1)
        self.assertEqual(updated.address.street_number, self.street_number)
        self.assertEqual((updated.address.stair, updated.address.floor, updated.address.door), ('B', 'BX', '2'))
        self.assertEqual(updated.address.address_extra, 'BATERIA')
        self.assertTrue(LogSupplyPointChange.objects.filter(supply_point=updated, action='address').exists())

    def test_crear_amb_adreca_com_a_dict(self):
        serializer = SupplyPointSerializer(data=self._payload('PORTELLA'), context=self.context)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()

        self.assertNotEqual(created.id, self.supply_point.id)
        self.assertEqual(created.address.street_number, self.street_number)
        self.assertEqual(created.property, self.property)
        self.assertEqual(created.cluster_nozzle.cluster, self.cluster)
