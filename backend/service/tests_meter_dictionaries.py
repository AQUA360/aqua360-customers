from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from service.models import Meter, MeterCommTechnology, MeterLog, MeterManufacturer, MeterModel
from service.utils.meter_dictionary_service import get_or_create_dictionary_value


class MeterDictionaryTests(TestCase):
    def test_dictionary_values_are_trimmed_and_reused_case_insensitively(self):
        first, created = get_or_create_dictionary_value(MeterManufacturer, '  Acme  ')
        second, reused = get_or_create_dictionary_value(MeterManufacturer, 'acme')

        self.assertTrue(created)
        self.assertFalse(reused)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.name, 'Acme')
        self.assertEqual(MeterManufacturer.objects.count(), 1)

    def test_models_are_scoped_to_their_manufacturer(self):
        first_manufacturer = MeterManufacturer.objects.create(name='Acme')
        second_manufacturer = MeterManufacturer.objects.create(name='Other')

        first_model, _ = get_or_create_dictionary_value(
            MeterModel,
            'A1',
            manufacturer=first_manufacturer,
        )
        second_model, _ = get_or_create_dictionary_value(
            MeterModel,
            'A1',
            manufacturer=second_manufacturer,
        )

        self.assertNotEqual(first_model.id, second_model.id)
        self.assertEqual(first_model.manufacturer_id, first_manufacturer.id)
        self.assertEqual(second_model.manufacturer_id, second_manufacturer.id)

    def test_communication_technology_uses_the_same_dictionary_service(self):
        first, created = get_or_create_dictionary_value(MeterCommTechnology, '  NB-IoT ')
        second, reused = get_or_create_dictionary_value(MeterCommTechnology, 'nb-iot')

        self.assertTrue(created)
        self.assertFalse(reused)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.name, 'NB-IoT')

    def test_invalid_names_are_rejected(self):
        for name in (None, False, 0, 42, [], {}, '', '   '):
            with self.subTest(name=name), self.assertRaises(ValueError):
                get_or_create_dictionary_value(MeterManufacturer, name)
        self.assertFalse(MeterManufacturer.objects.exists())

    def test_normalized_names_respect_the_field_length_limit(self):
        for model in (MeterManufacturer, MeterModel, MeterCommTechnology):
            with self.subTest(model=model):
                name = 'é' * model._meta.get_field('name').max_length
                value, created = get_or_create_dictionary_value(model, f'  {name}  ')

                self.assertTrue(created)
                self.assertEqual(value.name, name)
                with self.assertRaises(ValueError):
                    get_or_create_dictionary_value(model, f'  {name}é  ')
                self.assertEqual(model.objects.count(), 1)

    def test_database_rejects_case_insensitive_duplicates(self):
        manufacturer = MeterManufacturer.objects.create(name='Acme')
        for model, filters in (
            (MeterManufacturer, {}),
            (MeterCommTechnology, {}),
            (MeterModel, {'manufacturer': manufacturer}),
            (MeterModel, {'manufacturer': None}),
        ):
            with self.subTest(model=model, filters=filters):
                if model != MeterManufacturer:
                    model.objects.create(name='Acme', **filters)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    model.objects.create(name='acme', **filters)

    def test_unrelated_integrity_errors_are_not_hidden(self):
        with patch.object(MeterManufacturer.objects, 'create', side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                get_or_create_dictionary_value(MeterManufacturer, 'Acme')

    def test_unicode_lookup_and_database_uniqueness_agree(self):
        first, _ = get_or_create_dictionary_value(MeterManufacturer, 'I')
        reused, created = get_or_create_dictionary_value(MeterManufacturer, 'ı')

        self.assertFalse(created)
        self.assertEqual(first.pk, reused.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MeterManufacturer.objects.create(name='ı')

    def test_meter_save_reuses_dictionary_names_case_insensitively(self):
        manufacturer = MeterManufacturer.objects.create(name='Acme')
        MeterModel.objects.create(name='A1', manufacturer=manufacturer)

        Meter.objects.create(code='DICTIONARY-TEST', manufacturer='acme', model='a1')

        self.assertEqual(MeterManufacturer.objects.count(), 1)
        self.assertEqual(MeterModel.objects.count(), 1)

    def test_raw_meter_load_does_not_populate_dictionaries(self):
        meter = Meter(code='DICTIONARY-RAW', manufacturer='Acme', model='A1')
        meter.save_base(raw=True)

        self.assertFalse(MeterManufacturer.objects.exists())
        self.assertFalse(MeterModel.objects.exists())


class MeterDictionaryAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='dictionary-user', is_superuser=True)
        cls.manufacturer = MeterManufacturer.objects.create(name='Acme')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def dictionary_endpoints(self):
        return (
            ('meter-manufacturer', {}),
            ('meter-model', {'manufacturer_id': self.manufacturer.pk}),
            ('meter-comm-technology', {}),
        )

    def test_created_and_existing_values_have_distinct_statuses(self):
        for endpoint, filters in self.dictionary_endpoints():
            with self.subTest(endpoint=endpoint):
                url = f'/service/{endpoint}/get-or-create/'
                created = self.client.post(url, {'name': '  New Value  ', **filters}, format='json')
                reused = self.client.post(url, {'name': 'new value', **filters}, format='json')

                self.assertEqual(created.status_code, 201)
                self.assertEqual(reused.status_code, 200)
                self.assertEqual(created.data['id'], reused.data['id'])
                self.assertEqual(created.data['name'], 'New Value')

    def test_invalid_names_return_400_for_every_dictionary(self):
        for endpoint, filters in self.dictionary_endpoints():
            for name in (None, False, 0, 42, [], {}, '', '   ', 'x' * 256):
                with self.subTest(endpoint=endpoint, name=name):
                    response = self.client.post(
                        f'/service/{endpoint}/get-or-create/',
                        {'name': name, **filters},
                        format='json',
                    )
                    self.assertEqual(response.status_code, 400)

    def test_technology_allows_full_crud(self):
        url = '/service/meter-comm-technology/'
        created = self.client.post(url, {'name': '  NB-IoT  '}, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['name'], 'NB-IoT')

        detail = f"{url}{created.data['id']}/"
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.patch(detail, {'name': 'LoRaWAN'}, format='json').status_code, 200)
        self.assertEqual(MeterCommTechnology.objects.get().name, 'LoRaWAN')
        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertFalse(MeterCommTechnology.objects.exists())


class MeterDictionaryCrudAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='dictionary-crud-user', is_superuser=True)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.manufacturer = MeterManufacturer.objects.create(name='Acme')

    def endpoints(self):
        return (
            ('meter-manufacturer', {}),
            ('meter-model', {'manufacturer': self.manufacturer.pk}),
            ('meter-comm-technology', {}),
        )

    def test_create_trims_and_keeps_typed_casing(self):
        for endpoint, extra in self.endpoints():
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    f'/service/{endpoint}/', {'name': '  Mixed Case  ', **extra}, format='json'
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.data['name'], 'Mixed Case')

    def test_case_insensitive_duplicates_return_400(self):
        for endpoint, extra in self.endpoints():
            with self.subTest(endpoint=endpoint):
                url = f'/service/{endpoint}/'
                self.assertEqual(self.client.post(url, {'name': 'Dup', **extra}, format='json').status_code, 201)
                response = self.client.post(url, {'name': ' dUP ', **extra}, format='json')
                self.assertEqual(response.status_code, 400)
                self.assertIn('name', response.data)

    def test_rename_onto_existing_name_returns_400(self):
        for endpoint, extra in self.endpoints():
            with self.subTest(endpoint=endpoint):
                url = f'/service/{endpoint}/'
                self.client.post(url, {'name': 'Taken', **extra}, format='json')
                other = self.client.post(url, {'name': 'Free', **extra}, format='json')
                response = self.client.patch(f"{url}{other.data['id']}/", {'name': 'TAKEN'}, format='json')
                self.assertEqual(response.status_code, 400)

    def test_rename_changing_only_case_is_allowed(self):
        response = self.client.patch(
            f'/service/meter-manufacturer/{self.manufacturer.pk}/', {'name': 'ACME'}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.manufacturer.refresh_from_db()
        self.assertEqual(self.manufacturer.name, 'ACME')

    def test_invalid_names_return_400(self):
        for endpoint, extra in self.endpoints():
            for name in (None, '', '   ', 'x' * 256):
                with self.subTest(endpoint=endpoint, name=name):
                    response = self.client.post(f'/service/{endpoint}/', {'name': name, **extra}, format='json')
                    self.assertEqual(response.status_code, 400)

    def test_model_requires_a_manufacturer(self):
        response = self.client.post('/service/meter-model/', {'name': 'Orphan'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('manufacturer', response.data)

    def test_model_manufacturer_cannot_be_changed(self):
        other = MeterManufacturer.objects.create(name='Other')
        model = MeterModel.objects.create(name='A1', manufacturer=self.manufacturer)
        response = self.client.patch(f'/service/meter-model/{model.pk}/', {'manufacturer': other.pk}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_models_can_be_listed_by_manufacturer(self):
        other = MeterManufacturer.objects.create(name='Other')
        MeterModel.objects.create(name='A1', manufacturer=self.manufacturer)
        MeterModel.objects.create(name='B1', manufacturer=other)
        response = self.client.get(f'/service/meter-model/?manufacturer={self.manufacturer.pk}')
        self.assertEqual([item['name'] for item in response.data['results']], ['A1'])

    def test_lists_are_not_truncated_to_the_default_page_size(self):
        MeterCommTechnology.objects.bulk_create(MeterCommTechnology(name=f'Tech {i:03}') for i in range(60))
        response = self.client.get('/service/meter-comm-technology/')
        self.assertEqual(len(response.data['results']), 60)


class MeterDictionaryRenameAndDeleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='dictionary-rename-user', is_superuser=True)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.acme = MeterManufacturer.objects.create(name='Acme')
        self.other = MeterManufacturer.objects.create(name='Other')
        self.acme_a1 = MeterModel.objects.create(name='A1', manufacturer=self.acme)
        self.other_a1 = MeterModel.objects.create(name='A1', manufacturer=self.other)
        self.tech = MeterCommTechnology.objects.create(name='NB-IoT')
        self.acme_meter = Meter.objects.create(
            code='RENAME-1', manufacturer='acme', model='a1', comm_technology='nb-iot'
        )
        self.other_meter = Meter.objects.create(
            code='RENAME-2', manufacturer='Other', model='A1', comm_technology='LoRaWAN'
        )

    def test_manufacturer_rename_propagates_to_meters_and_logs_it(self):
        response = self.client.patch(
            f'/service/meter-manufacturer/{self.acme.pk}/', {'name': 'Acme Water'}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.acme_meter.refresh_from_db()
        self.other_meter.refresh_from_db()
        self.assertEqual(self.acme_meter.manufacturer, 'Acme Water')
        self.assertEqual(self.other_meter.manufacturer, 'Other')
        log = MeterLog.objects.get(meter=self.acme_meter, field_name='manufacturer')
        self.assertEqual((log.old_value, log.new_value, log.user), ('acme', 'Acme Water', self.user))

    def test_model_rename_only_touches_meters_of_its_manufacturer(self):
        response = self.client.patch(f'/service/meter-model/{self.acme_a1.pk}/', {'name': 'A2'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.acme_meter.refresh_from_db()
        self.other_meter.refresh_from_db()
        self.assertEqual(self.acme_meter.model, 'A2')
        self.assertEqual(self.other_meter.model, 'A1')

    def test_technology_rename_propagates_to_meters(self):
        response = self.client.patch(
            f'/service/meter-comm-technology/{self.tech.pk}/', {'name': 'NB-IoT v2'}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.acme_meter.refresh_from_db()
        self.other_meter.refresh_from_db()
        self.assertEqual(self.acme_meter.comm_technology, 'NB-IoT v2')
        self.assertEqual(self.other_meter.comm_technology, 'LoRaWAN')

    def test_values_in_use_cannot_be_deleted(self):
        for endpoint, pk in (
            ('meter-manufacturer', self.acme.pk),
            ('meter-model', self.acme_a1.pk),
            ('meter-comm-technology', self.tech.pk),
        ):
            with self.subTest(endpoint=endpoint):
                response = self.client.delete(f'/service/{endpoint}/{pk}/')
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['meters_count'], 1)
        self.assertTrue(MeterManufacturer.objects.filter(pk=self.acme.pk).exists())
        self.assertTrue(MeterModel.objects.filter(pk=self.acme_a1.pk).exists())
        self.assertTrue(MeterCommTechnology.objects.filter(pk=self.tech.pk).exists())

    def test_model_without_manufacturer_only_matches_meters_without_manufacturer(self):
        orphan = MeterModel.objects.create(name='A1', manufacturer=None)
        orphan_meter = Meter.objects.create(code='RENAME-3', manufacturer=None, model='a1')

        response = self.client.delete(f'/service/meter-model/{orphan.pk}/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['meters_count'], 1)

        response = self.client.patch(f'/service/meter-model/{orphan.pk}/', {'name': 'A3'}, format='json')
        self.assertEqual(response.status_code, 200)
        orphan_meter.refresh_from_db()
        self.acme_meter.refresh_from_db()
        self.other_meter.refresh_from_db()
        self.assertEqual(orphan_meter.model, 'A3')
        self.assertEqual(self.acme_meter.model, 'a1')
        self.assertEqual(self.other_meter.model, 'A1')

    def test_meter_values_with_surrounding_spaces_are_matched(self):
        padded_meter = Meter.objects.bulk_create([
            Meter(code='RENAME-4', manufacturer='  ACME ', model=' A1  ', comm_technology=' nb-iot ')
        ])[0]

        response = self.client.delete(f'/service/meter-comm-technology/{self.tech.pk}/')
        self.assertEqual(response.data['meters_count'], 2)

        self.client.patch(f'/service/meter-model/{self.acme_a1.pk}/', {'name': 'A2'}, format='json')
        padded_meter.refresh_from_db()
        self.assertEqual(padded_meter.model, 'A2')

    def test_unused_values_can_be_deleted(self):
        self.acme_meter.delete()
        for endpoint, pk in (
            ('meter-model', self.acme_a1.pk),
            ('meter-manufacturer', self.acme.pk),
            ('meter-comm-technology', self.tech.pk),
        ):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.client.delete(f'/service/{endpoint}/{pk}/').status_code, 204)


class MeterDictionaryConcurrencyTests(TransactionTestCase):
    def test_concurrent_insertion_returns_the_same_record(self):
        manufacturer = MeterManufacturer.objects.create(name='Acme')
        for model, filters in (
            (MeterManufacturer, {}),
            (MeterCommTechnology, {}),
            (MeterModel, {'manufacturer': manufacturer}),
            (MeterModel, {'manufacturer': None}),
        ):
            with self.subTest(model=model, filters=filters):
                barrier = Barrier(2)
                create = model.objects.create

                def concurrent_create(**kwargs):
                    barrier.wait(timeout=10)
                    return create(**kwargs)

                def get_value(name):
                    try:
                        value, created = get_or_create_dictionary_value(model, name, **filters)
                        return value.pk, created
                    finally:
                        connections.close_all()

                with patch.object(model.objects, 'create', side_effect=concurrent_create):
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        results = list(executor.map(get_value, ('Race', 'race')))

                self.assertEqual(results[0][0], results[1][0])
                self.assertCountEqual([result[1] for result in results], [True, False])


class MeterDictionaryMigrationTests(TransactionTestCase):
    def test_existing_duplicates_are_merged_before_constraints_are_added(self):
        previous = [('service', '0136_metercommtechnology')]
        current = [('service', '0138_meter_dictionary_constraints')]
        executor = MigrationExecutor(connection)
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            manufacturer_model = apps.get_model('service', 'MeterManufacturer')
            meter_model = apps.get_model('service', 'MeterModel')
            technology_model = apps.get_model('service', 'MeterCommTechnology')
            first = manufacturer_model.objects.create(name='Acme')
            duplicate = manufacturer_model.objects.create(name='ACME')
            other = manufacturer_model.objects.create(name='Other')
            first_model = meter_model.objects.create(name='A1', manufacturer=first)
            meter_model.objects.create(name='a1', manufacturer=duplicate)
            moved_model = meter_model.objects.create(name='B1', manufacturer=duplicate)
            separate_model = meter_model.objects.create(name='a1', manufacturer=other)
            orphan = meter_model.objects.create(name='X1')
            meter_model.objects.create(name='x1')
            technology = technology_model.objects.create(name='NB-IoT')
            technology_model.objects.create(name='nb-iot')

            executor = MigrationExecutor(connection)
            executor.migrate(current)

            self.assertFalse(MeterManufacturer.objects.filter(pk=duplicate.pk).exists())
            self.assertEqual(MeterModel.objects.get(pk=moved_model.pk).manufacturer_id, first.pk)
            self.assertCountEqual(
                MeterModel.objects.filter(manufacturer_id=first.pk).values_list('pk', flat=True),
                [first_model.pk, moved_model.pk],
            )
            self.assertTrue(MeterModel.objects.filter(pk=separate_model.pk).exists())
            self.assertEqual(list(MeterModel.objects.filter(manufacturer=None).values_list('pk', flat=True)), [orphan.pk])
            self.assertEqual(list(MeterCommTechnology.objects.values_list('pk', flat=True)), [technology.pk])
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
