from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from service.models import Meter, MeterCommTechnology, MeterManufacturer, MeterModel


class PopulateMeterDictionariesCommandTests(TestCase):
    def setUp(self):
        # bulk_create evita el post_save, com passa amb les importacions massives:
        # és justament el cas que l'ordre ha de cobrir.
        Meter.objects.bulk_create([
            Meter(code='POP-1', manufacturer='  Acme ', model=' A1 ', comm_technology='  NB-IoT '),
            Meter(code='POP-2', manufacturer='ACME', model='a1', comm_technology='nb-iot'),
            Meter(code='POP-3', manufacturer='Other', model='A1', comm_technology='LoRaWAN'),
            Meter(code='POP-4', manufacturer='', model=None, comm_technology='   '),
            Meter(code='POP-5', manufacturer=None, model='Orphan', comm_technology=None),
        ])

    def run_command(self, *args):
        out = StringIO()
        call_command('populate_meter_dictionaries', *args, stdout=out)
        return out.getvalue()

    def test_creates_normalized_unique_values(self):
        self.run_command()

        self.assertEqual(sorted(MeterManufacturer.objects.values_list('name', flat=True)), ['Acme', 'Other'])
        self.assertEqual(sorted(MeterCommTechnology.objects.values_list('name', flat=True)), ['LoRaWAN', 'NB-IoT'])
        self.assertEqual(
            sorted(MeterModel.objects.values_list('manufacturer__name', 'name')),
            [('Acme', 'A1'), ('Other', 'A1')],
        )

    def test_is_idempotent(self):
        self.run_command()
        counts = (MeterManufacturer.objects.count(), MeterModel.objects.count(), MeterCommTechnology.objects.count())

        output = self.run_command()

        self.assertEqual(
            (MeterManufacturer.objects.count(), MeterModel.objects.count(), MeterCommTechnology.objects.count()),
            counts,
        )
        self.assertIn('MeterCommTechnology: 2 valors trobats, 0 creats, 2 ja existents.', output)

    def test_reuses_existing_values_regardless_of_case(self):
        existing = MeterCommTechnology.objects.create(name='nb-iot')

        self.run_command('--only', 'comm_technology')

        self.assertEqual(
            list(MeterCommTechnology.objects.order_by('name').values_list('name', flat=True)),
            ['LoRaWAN', 'nb-iot'],
        )
        self.assertTrue(MeterCommTechnology.objects.filter(pk=existing.pk).exists())

    def test_dry_run_writes_nothing(self):
        output = self.run_command('--dry-run')

        self.assertIn('DRY RUN', output)
        self.assertFalse(MeterManufacturer.objects.exists())
        self.assertFalse(MeterModel.objects.exists())
        self.assertFalse(MeterCommTechnology.objects.exists())

    def test_only_limits_the_populated_dictionaries(self):
        self.run_command('--only', 'comm_technology')

        self.assertTrue(MeterCommTechnology.objects.exists())
        self.assertFalse(MeterManufacturer.objects.exists())
        self.assertFalse(MeterModel.objects.exists())

    def test_reports_models_without_manufacturer_as_skipped(self):
        output = self.run_command()

        self.assertIn('MeterModel: 1 combinacions omeses', output)
