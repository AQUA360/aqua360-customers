from django.test import TestCase

from service.models import MeterCommTechnology, MeterManufacturer, MeterModel
from service.utils.meter_dictionary_service import get_or_create_dictionary_value


class MeterDictionaryTests(TestCase):
    def test_dictionary_values_are_trimmed_and_reused_case_insensitively(self):
        first = get_or_create_dictionary_value(MeterManufacturer, '  Acme  ')
        second = get_or_create_dictionary_value(MeterManufacturer, 'acme')

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.name, 'Acme')
        self.assertEqual(MeterManufacturer.objects.count(), 1)

    def test_models_are_scoped_to_their_manufacturer(self):
        first_manufacturer = MeterManufacturer.objects.create(name='Acme')
        second_manufacturer = MeterManufacturer.objects.create(name='Other')

        first_model = get_or_create_dictionary_value(
            MeterModel,
            'A1',
            manufacturer=first_manufacturer,
        )
        second_model = get_or_create_dictionary_value(
            MeterModel,
            'A1',
            manufacturer=second_manufacturer,
        )

        self.assertNotEqual(first_model.id, second_model.id)
        self.assertEqual(first_model.manufacturer_id, first_manufacturer.id)
        self.assertEqual(second_model.manufacturer_id, second_manufacturer.id)

    def test_communication_technology_uses_the_same_dictionary_service(self):
        first = get_or_create_dictionary_value(MeterCommTechnology, '  NB-IoT ')
        second = get_or_create_dictionary_value(MeterCommTechnology, 'nb-iot')

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.name, 'NB-IoT')
