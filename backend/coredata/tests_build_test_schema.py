import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from coredata.management.commands.build_test_schema import (
    Command,
    migrations_not_in_graph,
    read_migration_manifest,
    stale_migration_files,
    write_migration_manifest,
)


class MigrationsNotInGraphTests(SimpleTestCase):
    def test_reports_applied_migrations_this_code_does_not_know(self):
        applied = {
            ("billing", "0001_initial"): object(),
            ("billing", "0099_future"): object(),
        }
        known = {("billing", "0001_initial"): object()}

        self.assertEqual(
            migrations_not_in_graph(applied, known),
            ["billing.0099_future"],
        )

    def test_empty_when_the_dump_is_an_ancestor(self):
        known = {
            ("billing", "0001_initial"): object(),
            ("billing", "0002_next"): object(),
        }
        applied = {("billing", "0001_initial"): object()}

        self.assertEqual(migrations_not_in_graph(applied, known), [])


class MigrationManifestTests(SimpleTestCase):
    def test_roundtrip_and_stale_detection(self):
        recorded = {("billing", "0001_initial"): "a" * 64}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schema.sql"
            path.write_text("-- schema\n", encoding="utf-8")
            write_migration_manifest(path, recorded)
            self.assertEqual(read_migration_manifest(path), recorded)
            write_migration_manifest(path, {("billing", "0002_next"): "b" * 64})
            self.assertEqual(
                read_migration_manifest(path),
                {("billing", "0002_next"): "b" * 64},
            )

        self.assertEqual(
            stale_migration_files(recorded, {("billing", "0001_initial"): "a" * 64}),
            [],
        )
        self.assertEqual(
            stale_migration_files(recorded, {("billing", "0001_initial"): "b" * 64}),
            ["billing.0001_initial"],
        )
        self.assertEqual(stale_migration_files({}, recorded), [])


class ReuseDumpTests(SimpleTestCase):
    def setUp(self):
        self.command = Command()
        self.hashes = {("billing", "0001_initial"): "a" * 64}
        self.connection = Mock()
        self.connection.settings_dict = {"NAME": "source"}
        self.settings = Mock()
        self.settings.DATABASES = {"default": {"NAME": "source"}}
        self.patches = [
            patch(
                "coredata.management.commands.build_test_schema.connection",
                self.connection,
            ),
            patch(
                "coredata.management.commands.build_test_schema.settings",
                self.settings,
            ),
            patch(
                "coredata.management.commands.build_test_schema.load_sql_file",
            ),
            patch(
                "coredata.management.commands.build_test_schema.MigrationExecutor",
            ),
            patch(
                "coredata.management.commands.build_test_schema.call_command",
            ),
            patch.object(self.command, "_recreate_build_database"),
            patch(
                "coredata.management.commands.build_test_schema.migration_hashes",
                return_value=self.hashes,
            ),
        ]
        started = [item.start() for item in self.patches]
        self.addCleanup(lambda: [item.stop() for item in self.patches])
        (
            self.connection_patch,
            self.settings_patch,
            self.load,
            self.executor_cls,
            self.migrate,
            self.recreate,
            self.hashes_mock,
        ) = started
        self.executor = self.executor_cls.return_value
        self.executor.loader.applied_migrations = {
            ("billing", "0001_initial"): object()
        }
        self.executor.loader.graph.nodes = {
            ("billing", "0001_initial"): object()
        }
        self.executor.loader.graph.leaf_nodes.return_value = [
            ("billing", "0001_initial")
        ]
        self.executor.migration_plan.return_value = []

    def _dump(self, contents="-- schema\n", manifest=True):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "schema.sql"
        path.write_text(contents, encoding="utf-8")
        if manifest:
            write_migration_manifest(path, self.hashes)
        return path

    def test_missing_dump_rebuilds_from_scratch(self):
        self.assertIsNone(self.command._try_reuse("", 1))
        self.assertIsNone(self.command._try_reuse("/no/existeix.sql", 1))
        empty = self._dump("", manifest=False)
        self.assertIsNone(self.command._try_reuse(str(empty), 1))
        self.load.assert_not_called()
        self.migrate.assert_not_called()
        self.recreate.assert_not_called()

    def test_legacy_dump_without_manifest_can_be_reused(self):
        legacy = self._dump("-- sense manifest\n", manifest=False)

        self.assertEqual(self.command._try_reuse(str(legacy), 1), "current")

        self.load.assert_called_once()
        self.recreate.assert_not_called()

    def test_edited_migration_is_not_reused(self):
        path = self._dump()
        self.hashes_mock.return_value = {
            ("billing", "0001_initial"): "b" * 64
        }

        self.assertIsNone(self.command._try_reuse(str(path), 1))

        self.load.assert_not_called()
        self.recreate.assert_called_once_with()

    def test_ancestor_dump_without_pending_migrations_is_kept(self):
        path = self._dump()

        self.assertEqual(self.command._try_reuse(str(path), 1), "current")

        self.load.assert_not_called()
        self.migrate.assert_not_called()
        self.recreate.assert_not_called()

    def test_ancestor_dump_applies_only_pending_migrations(self):
        path = self._dump()
        self.hashes_mock.return_value = {
            **self.hashes,
            ("billing", "0002_next"): "c" * 64,
        }
        self.executor.migration_plan.return_value = [("billing.0002_next", False)]

        self.assertEqual(self.command._try_reuse(str(path), 1), "updated")

        self.migrate.assert_called_once_with("migrate", interactive=False, verbosity=1)
        self.recreate.assert_not_called()

    def test_newer_dump_is_rejected_so_it_is_not_saved_for_this_code(self):
        path = self._dump(manifest=False)
        self.executor.loader.applied_migrations = {
            ("billing", "0001_initial"): object(),
            ("billing", "0099_future"): object(),
        }

        self.assertIsNone(self.command._try_reuse(str(path), 1))

        self.migrate.assert_not_called()
        self.recreate.assert_called_once_with()
        self.assertEqual(self.settings.DATABASES["default"]["NAME"], "schema_build")

    def test_failed_restore_falls_back_to_an_empty_database(self):
        path = self._dump()
        self.hashes_mock.return_value = {
            **self.hashes,
            ("billing", "0002_next"): "c" * 64,
        }
        self.load.side_effect = RuntimeError("psql ha petat")

        self.assertIsNone(self.command._try_reuse(str(path), 1))

        self.migrate.assert_not_called()
        self.recreate.assert_called_once_with()

    def test_publish_copies_when_the_output_is_a_different_file(self):
        source = self._dump("-- ja migrat\n", manifest=False)
        target_dir = tempfile.TemporaryDirectory()
        self.addCleanup(target_dir.cleanup)
        target = Path(target_dir.name) / "out" / "schema.sql"

        self.command._publish_existing_dump(str(source), str(target))

        self.assertEqual(target.read_text(encoding="utf-8"), "-- ja migrat\n")

    def test_publish_keeps_the_file_when_it_is_already_the_output(self):
        source = self._dump("-- ja migrat\n", manifest=False)

        self.command._publish_existing_dump(str(source), str(source))

        self.assertEqual(source.read_text(encoding="utf-8"), "-- ja migrat\n")
