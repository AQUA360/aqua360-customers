import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from . import creation, schema_dump


class TestSchemaDatabaseCreationTests(TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.schema = Path(directory.name) / "schema.sql"
        self.schema.write_text("-- Test schema\n", encoding="utf-8")
        self.connection = Mock(
            alias="default",
            settings_dict={"NAME": "source", "TEST": {"NAME": None}},
        )
        self.creation = creation.TestSchemaDatabaseCreation(self.connection)
        self.settings = SimpleNamespace(
            DATABASES={"default": self.connection.settings_dict}
        )
        for patcher in (
            patch.dict(os.environ, TEST_SCHEMA_FILE=str(self.schema)),
            patch.object(creation, "settings", self.settings),
            patch.object(self.creation, "_create_test_db"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_serialization_after_schema_preparation_before_cache_table(self):
        for existing in (False, True):
            for serialize in (False, True):
                with self.subTest(existing=existing, serialize=serialize):
                    self.connection.reset_mock()
                    self.connection.settings_dict["NAME"] = "source"
                    self.connection.__dict__.pop("_test_serialized_contents", None)
                    events = []

                    def serialized_contents():
                        self.assertEqual(
                            self.connection.settings_dict["NAME"], "test_source"
                        )
                        self.assertEqual(events, [] if existing else ["load"])
                        events.append("serialize")
                        return "serialized migration data"

                    with (
                        patch.object(
                            self.creation,
                            "_has_migrations_table",
                            side_effect=[True] if existing else [False, True],
                        ),
                        patch.object(
                            creation, "load_sql_file",
                            side_effect=lambda *args: events.append("load"),
                        ) as load,
                        patch.object(
                            self.creation, "serialize_db_to_string",
                            side_effect=serialized_contents,
                        ) as dump,
                        patch.object(
                            creation, "call_command",
                            side_effect=lambda *args, **kwargs: events.append("cache"),
                        ) as cache,
                    ):
                        name = self.creation.create_test_db(
                            verbosity=0, serialize=serialize, keepdb=existing
                        )

                    self.assertEqual(name, "test_source")
                    self.assertEqual(load.call_count, int(not existing))
                    self.assertEqual(dump.call_count, int(serialize))
                    if serialize:
                        self.assertEqual(
                            self.connection._test_serialized_contents,
                            "serialized migration data",
                        )
                    else:
                        self.assertNotIn(
                            "_test_serialized_contents", self.connection.__dict__
                        )
                    self.assertEqual(
                        events,
                        ([] if existing else ["load"])
                        + (["serialize"] if serialize else [])
                        + ["cache"],
                    )
                    cache.assert_called_once_with("createcachetable", database="default")
                    self.connection.ensure_connection.assert_called_once_with()


class LoadSqlFileTests(TestCase):
    def test_restore_stops_on_error_and_uses_a_single_transaction(self):
        with (
            patch.object(schema_dump, "_require_client"),
            patch.object(schema_dump, "_run") as run,
        ):
            schema_dump.load_sql_file({}, "test_source", "schema.sql")

        command = run.call_args.args[0]
        self.assertEqual(command[0], "psql")
        self.assertIn("ON_ERROR_STOP=1", command)
        self.assertIn("--single-transaction", command)
