import os
import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from customers.test_db.schema_dump import SchemaDumpError, client_major, dump_database

BUILD_DATABASE = "schema_build"


class Command(BaseCommand):
    help = (
        "Aplica totes les migracions a una base temporal i escriu un abocament "
        "SQL amb l'estat final, per restaurar-lo a les proves sense tornar a "
        "migrar. Només amb customers.settings_test."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            required=True,
            help="Fitxer .sql de sortida, per exemple .ci/test_schema.sql",
        )

    def handle(self, *args, **options):
        if not settings.SETTINGS_MODULE.endswith("settings_test"):
            raise CommandError(
                "Aquesta ordre només es pot executar amb customers.settings_test."
            )

        major = client_major()
        if major is None:
            raise CommandError(
                "No s'ha trobat pg_dump. Cal el paquet postgresql-client."
            )
        if major != 16:
            self.stdout.write(
                self.style.WARNING(
                    f"pg_dump és de PostgreSQL {major} i el servidor de proves "
                    "és el 16. L'abocament es neteja, però el client hauria de "
                    "ser de la versió 16."
                )
            )

        original_name = settings.DATABASES["default"]["NAME"]
        output = options["output"]
        started = time.monotonic()
        try:
            self._recreate_build_database()
            settings.DATABASES["default"]["NAME"] = BUILD_DATABASE
            connection.settings_dict["NAME"] = BUILD_DATABASE
            connection.close()
            call_command(
                "migrate",
                interactive=False,
                verbosity=options["verbosity"],
            )
            connection.close()
            self.stdout.write(
                f"Migracions aplicades en {time.monotonic() - started:.0f}s. "
                "Escrivint l'abocament..."
            )
            partial = output + ".partial"
            try:
                try:
                    dump_database(connection.settings_dict, BUILD_DATABASE, partial)
                except SchemaDumpError as exc:
                    raise CommandError(str(exc)) from exc
                os.replace(partial, output)
            finally:
                if os.path.exists(partial):
                    os.remove(partial)
        finally:
            connection.close()
            settings.DATABASES["default"]["NAME"] = original_name
            connection.settings_dict["NAME"] = original_name
            self._drop_build_database()

        self.stdout.write(self.style.SUCCESS(f"Esquema de test escrit a {output}"))

    def _recreate_build_database(self):
        self._drop_build_database()
        quoted = connection.ops.quote_name(BUILD_DATABASE)
        with connection._nodb_cursor() as cursor:
            cursor.execute(f"CREATE DATABASE {quoted}")

    def _drop_build_database(self):
        connection.close()
        quoted = connection.ops.quote_name(BUILD_DATABASE)
        with connection._nodb_cursor() as cursor:
            cursor.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                [BUILD_DATABASE],
            )
            cursor.execute(f"DROP DATABASE IF EXISTS {quoted}")
