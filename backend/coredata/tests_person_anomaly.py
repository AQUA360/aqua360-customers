"""Anomalies de la persona (#2633): catàleg, alta, resolució, baixa i vigència."""
from datetime import timedelta

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from coredata.models import Person, PersonAnomaly, PersonAnomalyType, PersonLog
from coredata.serializers import PersonContractMinimalSerializer, current_person_anomalies
from coredata.views.person_anomaly_view import PersonAnomalyTypeViewSet, PersonAnomalyViewSet


def _perm(label):
    app_label, codename = label.split('.')
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class PersonAnomalyTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = User.objects.create_user('anomaly-editor-2633', 'anomaly-editor-2633@example.com', 'x')
        cls.editor.user_permissions.add(
            _perm('coredata.view_person'), _perm('coredata.add_person'),
            _perm('coredata.change_person'), _perm('coredata.delete_person'),
        )
        cls.viewer = User.objects.create_user('anomaly-viewer-2633', 'anomaly-viewer-2633@example.com', 'x')
        cls.viewer.user_permissions.add(_perm('coredata.view_person'))
        cls.person = Person.objects.create(token='PERSON-ANOMALY-2633', name='Prova')
        cls.insolvent = PersonAnomalyType.objects.get(token='insolvent')
        cls.wrong_iban = PersonAnomalyType.objects.get(token='wrong_iban')
        cls.factory = APIRequestFactory()
        cls.today = timezone.now().date()

    def _call(self, actions, method, user, data=None, **kwargs):
        request = getattr(self.factory, method)('/coredata/person-anomaly/', data or {}, format='json')
        force_authenticate(request, user=User.objects.get(pk=user.pk))
        return PersonAnomalyViewSet.as_view(actions)(request, **kwargs)

    def _create(self, user=None, **data):
        payload = {
            'person': self.person.id,
            'anomaly_type_id': self.wrong_iban.id,
            'start_date': self.today.isoformat(),
        }
        payload.update(data)
        return self._call({'post': 'create'}, 'post', user or self.editor, payload)

    def test_initial_types_are_created(self):
        tokens = set(PersonAnomalyType.objects.values_list('token', flat=True))
        self.assertTrue({'wrong_identification', 'wrong_iban', 'deceased', 'insolvent'} <= tokens)
        self.assertTrue(self.insolvent.opens_process)
        self.assertFalse(self.wrong_iban.opens_process)

    def test_types_list(self):
        request = self.factory.get('/coredata/person-anomaly-type/')
        force_authenticate(request, user=User.objects.get(pk=self.viewer.pk))
        response = PersonAnomalyTypeViewSet.as_view({'get': 'list'})(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('insolvent', [row['token'] for row in response.data])

    def test_create_sets_user_and_logs(self):
        response = self._create(observation='Concurs de creditors')
        self.assertEqual(response.status_code, 201, response.data)
        anomaly = PersonAnomaly.objects.get(pk=response.data['id'])
        self.assertEqual(anomaly.user_id, self.editor.id)
        self.assertTrue(response.data['is_current'])
        log = PersonLog.objects.get(person=self.person, field_name='anomaly')
        self.assertIsNone(log.old_value)
        self.assertIn('IBAN incorrecte', log.new_value)

    def test_create_requires_change_permission(self):
        self.assertEqual(self._create(user=self.viewer).status_code, 403)

    def test_resolve_requires_change_permission(self):
        anomaly_id = self._create().data['id']
        creator = User.objects.create_user('anomaly-creator-2633', 'anomaly-creator-2633@example.com', 'x')
        creator.user_permissions.add(_perm('coredata.view_person'), _perm('coredata.add_person'))
        response = self._call({'post': 'resolve'}, 'post', creator, {}, pk=anomaly_id)
        self.assertEqual(response.status_code, 403)
        changer = User.objects.create_user('anomaly-changer-2633', 'anomaly-changer-2633@example.com', 'x')
        changer.user_permissions.add(_perm('coredata.view_person'), _perm('coredata.change_person'))
        response = self._call({'post': 'resolve'}, 'post', changer, {}, pk=anomaly_id)
        self.assertEqual(response.status_code, 200, response.data)

    def test_observation_change_is_logged(self):
        anomaly_id = self._create(observation='Primera').data['id']
        response = self._call({'patch': 'partial_update'}, 'patch', self.editor, {'observation': 'Segona'}, pk=anomaly_id)
        self.assertEqual(response.status_code, 200, response.data)
        last_log = PersonLog.objects.filter(person=self.person, field_name='anomaly').order_by('-id').first()
        self.assertIn('Primera', last_log.old_value)
        self.assertIn('Segona', last_log.new_value)

    def test_types_require_person_read_permission(self):
        no_perms = User.objects.create_user('anomaly-noperms-2633', 'anomaly-noperms-2633@example.com', 'x')
        request = self.factory.get('/coredata/person-anomaly-type/')
        force_authenticate(request, user=no_perms)
        response = PersonAnomalyTypeViewSet.as_view({'get': 'list'})(request)
        self.assertEqual(response.status_code, 403)

    def test_process_types_cannot_be_created_directly(self):
        response = self._create(anomaly_type_id=self.insolvent.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('anomaly_type_id', response.data)

    def test_end_date_before_start_date_is_rejected(self):
        response = self._create(end_date=(self.today - timedelta(days=1)).isoformat())
        self.assertEqual(response.status_code, 400)
        self.assertIn('end_date', response.data)

    def test_resolve_ends_anomaly(self):
        anomaly_id = self._create().data['id']
        response = self._call({'post': 'resolve'}, 'post', self.editor, {}, pk=anomaly_id)
        self.assertEqual(response.status_code, 200, response.data)
        anomaly = PersonAnomaly.objects.get(pk=anomaly_id)
        self.assertEqual(anomaly.end_date, self.today)
        self.assertFalse(anomaly.is_current)
        self.assertEqual(current_person_anomalies(self.person), [])
        self.assertEqual(PersonLog.objects.filter(person=self.person, field_name='anomaly').count(), 2)

    def test_destroy_is_soft_and_logged(self):
        anomaly_id = self._create().data['id']
        response = self._call({'delete': 'destroy'}, 'delete', self.editor, pk=anomaly_id)
        self.assertEqual(response.status_code, 204)
        anomaly = PersonAnomaly.objects.get(pk=anomaly_id)
        self.assertFalse(anomaly.is_active)
        self.assertEqual(current_person_anomalies(self.person), [])
        list_response = self._call({'get': 'list'}, 'get', self.viewer, {'person_id': self.person.id})
        ids = [row['id'] for row in list_response.data.get('results', list_response.data)]
        self.assertNotIn(anomaly_id, ids)
        last_log = PersonLog.objects.filter(person=self.person, field_name='anomaly').order_by('-id').first()
        self.assertIsNone(last_log.new_value)

    def test_current_anomalies_in_contract_person(self):
        PersonAnomaly.objects.create(person=self.person, anomaly_type=self.wrong_iban, start_date=self.today,
                                     end_date=self.today + timedelta(days=10))
        PersonAnomaly.objects.create(person=self.person, anomaly_type=self.insolvent, start_date=self.today,
                                     end_date=self.today)
        # El camp del serialitzador de les persones del contracte (la representació sencera
        # necessita configuració que la BD de proves buida no té)
        rows = PersonContractMinimalSerializer().get_current_anomalies(self.person)
        self.assertEqual([row['token'] for row in rows], ['wrong_iban'])
