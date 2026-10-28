import os
import sys
import time

from django.conf import settings
from django.core.management import call_command
from django.db.backends.postgresql.creation import DatabaseCreation

from .schema_dump import SchemaDumpError, load_sql_file


class TestSchemaDatabaseCreation(DatabaseCreation):
    """Crea la base de test des d'un SQL ja migrat quan TEST_SCHEMA_FILE existeix."""

    def create_test_db(self, verbosity=1, autoclobber=False, serialize=True, keepdb=False):
        schema = os.environ.get("TEST_SCHEMA_FILE", "").strip()
        if not schema:
            return super().create_test_db(
                verbosity=verbosity,
                autoclobber=autoclobber,
                serialize=serialize,
                keepdb=keepdb,
            )

        if not os.path.isfile(schema):
            self.log(f"No s'ha trobat l'esquema de test: {schema}")
            sys.exit(2)

        test_database_name = self._get_test_db_name()
        if verbosity >= 1:
            action = "Using existing" if keepdb else "Creating"
            self.log(
                "%s test database for alias %s..."
                % (
                    action,
                    self._get_database_display_str(verbosity, test_database_name),
                )
            )

        self._create_test_db(verbosity, autoclobber, keepdb)
        self.connection.close()
        settings.DATABASES[self.connection.alias]["NAME"] = test_database_name
        self.connection.settings_dict["NAME"] = test_database_name

        # Les proves usen TestCase, que desfà els canvis amb una transacció.
        # Saltem la serialització posterior: rellegiria totes les taules i el
        # graf de migracions.
        if not self._has_migrations_table():
            if verbosity >= 1:
                self.log(
                    "Carregant l'esquema SQL sense aplicar migracions "
                    f"({schema})..."
                )
            started = time.monotonic()
            try:
                load_sql_file(self.connection.settings_dict, test_database_name, schema)
            except SchemaDumpError as exc:
                self.log(str(exc))
                sys.exit(2)
            self.connection.close()
            if not self._has_migrations_table():
                self.log("L'esquema SQL no ha creat la taula django_migrations.")
                sys.exit(2)
            if verbosity >= 1:
                self.log(
                    "Esquema de test carregat en "
                    f"{time.monotonic() - started:.0f}s."
                )
        elif verbosity >= 1:
            self.log("La base de test ja té esquema; no es torna a carregar.")

        call_command("createcachetable", database=self.connection.alias)
        self.connection.ensure_connection()
        return test_database_name

    def _has_migrations_table(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.django_migrations')")
            row = cursor.fetchone()
        return bool(row and row[0])
