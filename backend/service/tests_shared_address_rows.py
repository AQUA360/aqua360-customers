from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from coredata.models import Address, City, Street, StreetNumber, StreetNumberType, StreetType
from coredata.utils.address_utils import resolve_street_number
from service.models import (
    Cluster, ClusterNozzle, Meter, MeterCaliber, MeterStatus, SupplyPoint,
)
from service.serializers.cluster_nozzle_serializer import ClusterNozzleSaveSerializer
from service.serializers.cluster_serializer import ClusterSaveSerializer
from service.serializers.meter_serializer import MeterSerializer
from service.serializers.supply_point_serializer import SupplyPointSaveNozzleSerializer


class SharedAddressRowsBase(TestCase):
    """Carrers i números es comparteixen entre adreces: desar una entitat no els ha de modificar."""

    def setUp(self):
        request = APIRequestFactory().post('/', HTTP_HOST='localhost')
        request.user = User.objects.create(username='tester')
        self.context = {'request': request}

        self.city = City.objects.create(token='T1', name='Ciutat')
        self.street_type = StreetType.objects.create(abbreviation='C', name='Carrer', aca_abbreviation='CR')
        self.other_type = StreetType.objects.create(abbreviation='AV', name='Avinguda', aca_abbreviation='AV')
        self.street = Street.objects.create(name='Carrer Major', type=self.street_type, name_2='', city=self.city)
        self.other_street = Street.objects.create(name='Carrer Nou', type=self.street_type, name_2='', city=self.city)
        self.number_type = StreetNumberType.objects.get_or_create(type='N', defaults={'description': 'N'})[0]
        self.number_10 = StreetNumber.objects.create(street=self.street, number_type=self.number_type, number=10)
        # Adreça d'un punt que comparteix carrer i número
        self.shared_address = Address.objects.create(
            street=self.street, street_number=self.number_10, city=self.city, stair='B', floor='1', door='2',
        )

    def assertSharedRowsUntouched(self):
        self.street.refresh_from_db()
        self.number_10.refresh_from_db()
        self.assertEqual((self.street.name, self.street.type_id, self.street.city_id),
                         ('Carrer Major', self.street_type.id, self.city.id))
        self.assertEqual((self.number_10.street_id, self.number_10.number, self.number_10.number_type_id),
                         (self.street.id, 10, self.number_type.id))
        self.shared_address.refresh_from_db()
        self.assertEqual(self.shared_address.street_number_id, self.number_10.id)


class ResolveStreetNumberTests(SharedAddressRowsBase):

    def test_reaprofita_el_numero_si_coincideix(self):
        self.assertEqual(resolve_street_number(self.street, self.number_type, {'number': 10}, self.number_10.id),
                         self.number_10)

    def test_camps_absents_es_prenen_del_numero_existent(self):
        self.assertEqual(resolve_street_number(None, None, {}, self.number_10.id), self.number_10)

    def test_numero_diferent_no_modifica_el_compartit(self):
        result = resolve_street_number(self.street, self.number_type, {'number': 12}, self.number_10.id)
        self.assertNotEqual(result.id, self.number_10.id)
        self.assertEqual((result.street_id, result.number), (self.street.id, 12))
        self.assertSharedRowsUntouched()

    def test_carrer_diferent_no_mou_el_numero(self):
        result = resolve_street_number(self.other_street, self.number_type, {'number': 10}, self.number_10.id)
        self.assertNotEqual(result.id, self.number_10.id)
        self.assertEqual(result.street_id, self.other_street.id)
        self.assertSharedRowsUntouched()

    def test_reaprofita_un_numero_igual_existent(self):
        number_12 = StreetNumber.objects.create(street=self.street, number_type=self.number_type, number=12,
                                                number_suffix='')
        result = resolve_street_number(self.street, self.number_type, {'number': '12', 'number_suffix': None},
                                       self.number_10.id)
        self.assertEqual(result, number_12)


class NozzleAddressHelpersTests(SharedAddressRowsBase):

    def _address_data(self, number):
        return {
            'street': {'street_id': self.street.id, 'name': 'Un altre nom', 'type': {'abbreviation': 'AV'}},
            'street_number': {'street_number_id': self.number_10.id, 'number_type': {'type': 'N'}, 'number': number},
            'city': self.city.id,
            'postal_code': '', 'building': '', 'floor': '3', 'door': '1', 'stair': '',
        }

    def test_helpers_de_la_bateria_no_modifiquen_carrer_ni_numero(self):
        for create in (SupplyPointSaveNozzleSerializer()._create_address,
                       ClusterNozzleSaveSerializer()._create_address_from_data):
            with self.subTest(create=create.__qualname__):
                address = create(self._address_data(12))
                self.assertEqual(address.street_id, self.street.id)
                self.assertEqual(address.street_number.number, 12)
                self.assertNotEqual(address.street_number_id, self.number_10.id)
                self.assertSharedRowsUntouched()

    def test_helpers_reaprofiten_el_numero_si_no_canvia(self):
        for create in (SupplyPointSaveNozzleSerializer()._create_address,
                       ClusterNozzleSaveSerializer()._create_address_from_data):
            with self.subTest(create=create.__qualname__):
                address = create(self._address_data(10))
                self.assertEqual(address.street_number_id, self.number_10.id)
                self.assertSharedRowsUntouched()


class MeterAddressTests(SharedAddressRowsBase):

    def setUp(self):
        super().setUp()
        self.status = MeterStatus.objects.create(token='ACTIVE', name='Actiu')
        self.caliber = MeterCaliber.objects.create(token='13', name='13')

    def _payload(self, number, street_number_id=None):
        street_number = {'number_type_type': 'N', 'number': number}
        if street_number_id:
            street_number['street_number_id'] = street_number_id
        return {
            'code': 'M-1', 'status': self.status.id, 'caliber': self.caliber.id,
            'supply_points': [], 'sub_meters': [],
            # Tipus que no coincideix amb el del carrer (p. ex. el que retorna el cadastre)
            'address_street': {'street_id': self.street.id, 'name': 'Un altre nom',
                               'type_abbreviation': 'CL', 'type_name': 'Calle'},
            'address_street_number': street_number,
            'address_city': self.city.id,
        }

    def test_crear_comptador_no_modifica_carrer_ni_numero(self):
        serializer = MeterSerializer(data=self._payload(12, self.number_10.id), context=self.context)
        serializer.is_valid(raise_exception=True)
        meter = serializer.save()
        self.assertEqual(meter.address_street_id, self.street.id)
        self.assertEqual(meter.address_street_number.number, 12)
        self.assertSharedRowsUntouched()

    def test_editar_comptador_no_modifica_el_numero_compartit(self):
        meter = Meter.objects.create(code='M-1', status=self.status, caliber=self.caliber,
                                     address_street=self.street, address_street_number=self.number_10)
        serializer = MeterSerializer(meter, data=self._payload(12, self.number_10.id),
                                     context=self.context, partial=True)
        serializer.is_valid(raise_exception=True)
        meter = serializer.save()
        meter.refresh_from_db()
        self.assertEqual(meter.address_street_number.number, 12)
        self.assertNotEqual(meter.address_street_number_id, self.number_10.id)
        self.assertSharedRowsUntouched()


class ClusterSaveNozzlesTests(SharedAddressRowsBase):

    def test_desar_la_bateria_no_aplica_les_dades_reduides_dels_punts(self):
        cluster = Cluster.objects.create(token='B1', nb_nozzles=1, address_street=self.street,
                                         address_street_number=self.number_10)
        nozzle = ClusterNozzle.objects.create(cluster=cluster, token='B1/1', position=1, col=1)
        supply_point = SupplyPoint.objects.create(token='SP1', address=self.shared_address, cluster_nozzle=nozzle)

        # Format de lectura de ClusterNozzleSerializer: adreça sense carrer ni número
        reduced_sp = {'id': supply_point.id, 'token': 'ALTRE', 'placement': None,
                      'address': {'building': None, 'floor': '1', 'door': '2', 'stair': 'B'}}
        data = {'token': 'B1', 'nb_nozzles': 1,
                'nozzles': [{'id': nozzle.id, 'position': 1, 'supply_points': [reduced_sp],
                             'supplyPoint': reduced_sp}]}
        serializer = ClusterSaveSerializer(cluster, data=data, context=self.context, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        supply_point.refresh_from_db()
        self.assertEqual(supply_point.address_id, self.shared_address.id)
        self.assertEqual(supply_point.token, 'SP1')
        self.assertEqual(supply_point.cluster_nozzle_id, nozzle.id)
        self.assertSharedRowsUntouched()
