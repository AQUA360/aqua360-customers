from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from service.models import Meter, MeterCommTechnology, MeterManufacturer, MeterModel
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
            for name in (None, False, 0, 42, [], {}, '', '   '):
                with self.subTest(endpoint=endpoint, name=name):
                    response = self.client.post(
                        f'/service/{endpoint}/get-or-create/',
                        {'name': name, **filters},
                        format='json',
                    )
                    self.assertEqual(response.status_code, 400)

    def test_technology_only_allows_reading_and_validated_creation(self):
        technology = MeterCommTechnology.objects.create(name='NB-IoT')
        url = '/service/meter-comm-technology/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(f'{url}{technology.pk}/').status_code, 200)
        for method, target in (
            ('post', url),
            ('put', f'{url}{technology.pk}/'),
            ('patch', f'{url}{technology.pk}/'),
            ('delete', f'{url}{technology.pk}/'),
        ):
            with self.subTest(method=method):
                response = getattr(self.client, method)(target, {'name': 'Other'}, format='json')
                self.assertEqual(response.status_code, 405)
        technology.refresh_from_db()
        self.assertEqual(technology.name, 'NB-IoT')


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
            MigrationExecutor(connection).migrate(current)
