"""Camps nous de la sol·licitud d'escomesa: emplaçament, representant, sol·licitant i documents."""
import importlib
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from coredata.models import ConfigProject, Person, PersonContact
from documentmanager.models import Document
from service.models import (
    ConnectionDocumentationType,
    ConnectionRequest,
    ConnectionRequestBuildingType,
    ConnectionRequestDocumentationFile,
    ConnectionRequestRepresentativeType,
)
from service.serializers.connection_request_serializer import (
    ConnectionRequestSaveSerializer,
    ConnectionRequestSerializer,
)
from service.views.connection_request_building_type_view import ConnectionRequestBuildingTypeViewSet
from service.views.connection_request_view import ConnectionRequestViewSet


def _user(*codenames):
    user = User.objects.create(username='u' + '_'.join(codenames)[:40])
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    return User.objects.get(pk=user.pk)  # neteja la cache de permisos


class ConnectionRequestFieldsTest(TestCase):
    def setUp(self):
        ConfigProject.objects.create(token='invoice_type_invoice_token', value='invoice')
        self.person = Person.objects.create(token='00000000T', name='Titular', surname='Prova')
        self.representative = Person.objects.create(token='11111111H', name='Representant', surname='Prova')
        self.building_type = ConnectionRequestBuildingType.objects.create(token='single_family', name='Habitatge unifamiliar')
        self.representative_type = ConnectionRequestRepresentativeType.objects.create(token='installer', name='Instal·lador/a')
        self.request = ConnectionRequest.objects.create(
            token='REQ-1',
            person=self.person,
            address_floor='2',
            address_door='1',
            cadastral='0000000AA0000A0001AA',
            scope='rural',
            polygon='5',
            parcel='12',
            building_type=self.building_type,
            requester_type='natural_person',
            property_condition='owner',
            representative=self.representative,
            representative_type=self.representative_type,
        )

    def _save(self, data):
        serializer = ConnectionRequestSaveSerializer(self.request, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    def test_desa_els_camps_nous(self):
        self._save({'address_stair': 'B', 'scope': 'urban', 'requester_type': 'owners_community'})
        self.request.refresh_from_db()
        self.assertEqual(self.request.address_stair, 'B')
        self.assertEqual(self.request.scope, 'urban')
        self.assertEqual(self.request.requester_type, 'owners_community')
        self.assertEqual(self.request.address_floor, '2')

    def test_valor_de_choice_invalid_es_rebutja(self):
        serializer = ConnectionRequestSaveSerializer(self.request, data={'scope': 'lunar'}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn('scope', serializer.errors)

    def test_clear_fields_buida_nomes_els_camps_permesos(self):
        self._save({'clear_fields': 'cadastral,representative,representative_type,person,token'})
        self.request.refresh_from_db()
        self.assertIsNone(self.request.cadastral)
        self.assertIsNone(self.request.representative)
        self.assertIsNone(self.request.representative_type)
        # camps fora de la llista: no es toquen
        self.assertEqual(self.request.person, self.person)
        self.assertEqual(self.request.token, 'REQ-1')
        self.assertEqual(self.request.polygon, '5')

    def test_clear_fields_no_trepitja_un_valor_enviat(self):
        self._save({'clear_fields': 'cadastral', 'cadastral': 'NOU'})
        self.request.refresh_from_db()
        self.assertEqual(self.request.cadastral, 'NOU')

    def test_detall_inclou_contactes_representant_i_documents_actius(self):
        PersonContact.objects.create(person=self.person, phone='600000000', email='titular@example.com')
        PersonContact.objects.create(person=self.person, phone='600000001', is_active=False)
        doc_type = ConnectionDocumentationType.objects.create(name='Poder de representació')
        document = Document.objects.create(entity_id=self.request.id, service='hdd', document_name='poder.pdf')
        ConnectionRequestDocumentationFile.objects.create(connection_request=self.request, file=document, type=doc_type)
        # document esborrat del gestor documental (file=NULL) i fitxer desactivat: no surten
        ConnectionRequestDocumentationFile.objects.create(connection_request=self.request, file=None, type=doc_type)
        ConnectionRequestDocumentationFile.objects.create(connection_request=self.request, file=document, is_active=False)

        data = ConnectionRequestSerializer(self.request).data

        self.assertEqual([c['phone'] for c in data['person']['contacts']], ['600000000'])
        self.assertEqual(data['representative']['token'], '11111111H')
        self.assertEqual(data['representative_type']['token'], 'installer')
        self.assertEqual(data['building_type']['token'], 'single_family')
        self.assertEqual(len(data['documentation_files']), 1)
        self.assertEqual(data['documentation_files'][0]['type']['name'], 'Poder de representació')

    def test_save_file_crea_el_document_de_la_sollicitud(self):
        doc_type = ConnectionDocumentationType.objects.create(name='Escriptures')

        def fake_upload(*args, **kwargs):
            return Document.objects.create(entity=args[1], entity_id=args[3], service='hdd', document_name=args[7])

        view = ConnectionRequestViewSet.as_view({'put': 'save_file'})
        request = APIRequestFactory().put(
            f'/service/connection-request/{self.request.id}/save-file/',
            {'file': SimpleUploadedFile('escriptura prova.pdf', b'%PDF'), 'doc_type': doc_type.id},
            format='multipart',
        )
        force_authenticate(request, user=_user('view_connectionrequest', 'change_connectionrequest'))
        with mock.patch('service.views.connection_request_view.upload_document', side_effect=fake_upload):
            response = view(request, pk=self.request.id)

        self.assertEqual(response.status_code, 200, response.data)
        doc_file = ConnectionRequestDocumentationFile.objects.get(connection_request=self.request)
        self.assertEqual(doc_file.type, doc_type)
        self.assertEqual(doc_file.file.entity, 'CONNECTION_REQUEST')
        self.assertEqual(doc_file.file.document_name, 'escriptura_prova.pdf')
        self.assertEqual(len(response.data['documentation_files']), 1)


class ConnectionRequestCatalogsTest(TestCase):
    def test_cataleg_requereix_permis_de_sollicitud(self):
        ConnectionRequestBuildingType.objects.create(token='other', name='Altres')
        view = ConnectionRequestBuildingTypeViewSet.as_view({'get': 'list'})
        factory = APIRequestFactory()

        request = factory.get('/service/connection-request-building-type/')
        force_authenticate(request, user=_user('view_connectionrequest'))
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        request = factory.get('/service/connection-request-building-type/')
        force_authenticate(request, user=_user())
        self.assertEqual(view(request).status_code, 403)

    def test_opscript_carrega_els_catalegs_sense_duplicar(self):
        ConnectionRequestBuildingType.objects.create(token='other', name='Nom personalitzat')
        opscript = importlib.import_module('service.opscripts.0001_load_connection_request_catalogs')
        opscript.run()
        opscript.run()

        self.assertEqual(ConnectionRequestBuildingType.objects.count(), 8)
        self.assertEqual(ConnectionRequestRepresentativeType.objects.count(), 7)
        self.assertEqual(ConnectionRequestBuildingType.objects.get(token='other').name, 'Nom personalitzat')
