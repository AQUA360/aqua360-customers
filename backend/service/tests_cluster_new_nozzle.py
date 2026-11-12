from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory

from fraud.models import FraudStatus

from coredata.models import ConfigProject, City, Country, Province, Street, StreetNumber, StreetNumberType, StreetType
from service.serializers.supply_point_serializer import SupplyPointSerializer
from service.models import (
    Cluster, ClusterNozzle, ClusterNozzleStatus, ClusterNozzleType, Connection, Property, SupplyPoint,
    SupplyPointPlacement, SupplyPointSource, SupplyPointStatus, SupplyPointSupplyType, SupplyPointType,
)


class ClusterNewNozzleFlowTests(TestCase):
    """Reprodueix el desat de la pantalla de bateria (ClusterEdit.vue) amb una boquilla nova."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_superuser('admin', 'a@a.test', 'x'))

        for token in ('fraud_status_pending_token', 'fraud_status_active_token', 'fraud_status_resolved_token',
                      'fraud_status_expired_token', 'contract_active_token', 'meter_status_active_token'):
            ConfigProject.objects.create(token=token, value=token)
            FraudStatus.objects.create(token=token, name=token)
        SupplyPointStatus.objects.create(token='ACTIVE', name='Actiu', is_default=True)
        self.nozzle_status = ClusterNozzleStatus.objects.create(token='OK', name='Actiu', is_default=True)
        self.nozzle_type = ClusterNozzleType.objects.create(token='STD', name='Estàndard', is_default=True)
        self.sp_type = SupplyPointType.objects.create(token='HAB', name='Habitatge')
        self.source = SupplyPointSource.objects.create(token='XARXA', name='Xarxa')
        self.supply_type = SupplyPointSupplyType.objects.create(token='DOM', name='Domèstic')
        self.placement = SupplyPointPlacement.objects.create(token='BATERIA', name='Bateria')

        country = Country.objects.create(name='Espanya', iso_code='ES')
        province = Province.objects.create(token='08', name='Barcelona', country=country)
        self.city = City.objects.create(token='T1', name='Ciutat', province=province)
        street_type = StreetType.objects.create(abbreviation='C', name='Carrer', aca_abbreviation='CR')
        self.street = Street.objects.create(name='Carrer Major', type=street_type, name_2='', city=self.city)
        number_type = StreetNumberType.objects.get_or_create(type='N', defaults={'description': 'N'})[0]
        self.number = StreetNumber.objects.create(street=self.street, number_type=number_type, number=6)

        self.property = Property.objects.create(token='P1', name='Finca')
        self.connection = Connection.objects.create(
            token='C1', address_street=self.street, address_street_number=self.number, address_city=self.city,
        )
        self.cluster = Cluster.objects.create(
            token='B1', nb_nozzles=2, connection=self.connection, property=self.property, is_active=True,
            address_street=self.street, address_street_number=self.number, address_city=self.city,
        )
        # Posicions amb forats i una boquilla fora de la graella, com les migrades
        self.n1 = ClusterNozzle.objects.create(cluster=self.cluster, token='B1/01', position=1, col=1, row=1)
        self.n2 = ClusterNozzle.objects.create(cluster=self.cluster, token='B1/15', position=15, col=99, row=99)
        SupplyPoint.objects.create(token='SP1', cluster_nozzle=self.n1, property=self.property)
        SupplyPoint.objects.create(token='SP2', cluster_nozzle=self.n2, property=self.property)

    def _save_cluster(self):
        data = {
            'id': self.cluster.id, 'connection': self.connection.id, 'token': 'B1', 'is_potable': True,
            'butlleti': None, 'usage_destination': None, 'address_extra': None, 'nb_nozzles': 3,
            'report_file': None, 'is_active': True,
            'address_city_id': self.city.id, 'address_street_id': self.street.id,
            'address_street_name': self.street.name, 'address_street_type_id': self.street.type_id,
            'address_street_number_id': self.number.id, 'address_street_number_number': 6,
        }
        response = self.client.put(f'/service/cluster/{self.cluster.id}/', data, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_alta_de_boquilla_nova_des_de_la_pantalla(self):
        cluster = self._save_cluster()
        street = dict(cluster['address_street'] or {})
        street.pop('type_abbreviation', None)
        street.pop('type_name', None)
        city = cluster['address_city']
        address = {
            'building': None, 'door': '2', 'stair': None, 'floor': 'LOCAL', 'address_extra': None,
            'street': {**street, 'street_id': street.get('id')},
            'street_number': {**(cluster['address_street_number'] or {}),
                              'street_number_id': (cluster['address_street_number'] or {}).get('id')},
            'city': city['id'], 'province': city['province']['id'], 'country': city['province']['country']['id'],
            'postal_code': (cluster.get('address_postal_code') or {}).get('code'),
        }
        # La creació del punt (SupplyPointViewSet.create) és el serializer; la resposta demana molta configuració
        request = APIRequestFactory().post('/', HTTP_HOST='localhost')
        request.user = User.objects.get(username='admin')
        serializer = SupplyPointSerializer(data={
            'connection_id': self.connection.id, 'property_id': (cluster.get('property') or {}).get('id'),
            'is_potable': True, 'token': '123456', 'type': self.sp_type.id, 'source': self.source.id,
            'placement_id': self.placement.id, 'supply_type': self.supply_type.id,
            'address_data': address, 'is_active': True,
        }, context={'request': request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        sp = {'id': serializer.save().id}

        nozzle_response = self.client.post('/service/cluster-nozzle/', {
            'diameter': None, 'status': self.nozzle_status.id, 'type': self.nozzle_type.id,
            'destination': 'LOCAL-2', 'position': 16, 'col': '5', 'row': '1',
            'destinationObject': {'floor': 'LOCAL', 'door': '2', 'stair': '', 'building': '', 'address_extra': ''},
            'cluster': self.cluster.id, 'token': 'B1/16', 'supply_point_id': sp['id'],
        }, format='json')
        self.assertEqual(nozzle_response.status_code, 201, nozzle_response.content)

        self.assertEqual(ClusterNozzle.objects.filter(cluster=self.cluster).count(), 3)
        self.assertEqual(SupplyPoint.objects.get(id=sp['id']).cluster_nozzle.position, 16)
