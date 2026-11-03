from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TestCase

from coredata.models import ConfigProject


class ContractMinPersonsConfigMigrationTests(TestCase):
    def run_migration(self):
        migration = import_module('coredata.migrations.0148_add_contract_min_persons_config')
        with connection.schema_editor() as schema_editor:
            migration.add_contract_min_persons_config(apps, schema_editor)

    def test_creates_missing_config_once(self):
        ConfigProject.objects.filter(token='contract_min_persons').delete()
        self.run_migration()
        self.run_migration()
        config = ConfigProject.objects.get(token='contract_min_persons')
        self.assertEqual(config.value, '3')
        self.assertTrue(config.name)

    def test_preserves_existing_config(self):
        ConfigProject.objects.filter(token='contract_min_persons').delete()
        config = ConfigProject.objects.create(
            token='contract_min_persons', value='7', name='Custom name', file='Custom file',
        )
        self.run_migration()
        self.assertEqual(ConfigProject.objects.filter(token='contract_min_persons').count(), 1)
        config.refresh_from_db()
        self.assertEqual(config.value, '7')
        self.assertEqual(config.name, 'Custom name')
        self.assertEqual(config.file, 'Custom file')
