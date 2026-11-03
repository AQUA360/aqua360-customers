import hashlib
import importlib
import os
import shutil
import time
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader

from customers.test_db.schema_dump import (
    SchemaDumpError,
    client_major,
    dump_database,
    load_sql_file,
)

BUILD_DATABASE = "schema_build"
MANIFEST_PREFIX = "-- aqua360-migration "


def migration_hashes():
    """SHA-256 de cada fitxer de migració que aquest codi carregaria."""
    hashes = {}
    for config in apps.get_app_configs():
        module_name, _explicit = MigrationLoader.migrations_module(config.label)
        if not module_name:
            continue
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        paths = getattr(module, "__path__", None)
        if not paths:
            continue
        directory = Path(paths[0])
        if not directory.is_dir():
            continue
        for file in directory.glob("*.py"):
            if file.name.startswith("_"):
                continue
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            hashes[(config.label, file.stem)] = digest
    return hashes


def read_migration_manifest(path):
    found = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith(MANIFEST_PREFIX):
                if found:
                    break
                continue
            parts = line[len(MANIFEST_PREFIX):].split()
            if len(parts) != 3:
                continue
            app, name, digest = parts
            found[(app, name)] = digest
    return found


def write_migration_manifest(path, hashes):
    block = "".join(
        f"{MANIFEST_PREFIX}{app} {name} {digest}\n"
        for (app, name), digest in sorted(hashes.items())
    )
    file = Path(path)
    lines = file.read_text(encoding="utf-8").splitlines(keepends=True)
    start = 0
    while start < len(lines) and lines[start].startswith(MANIFEST_PREFIX):
        start += 1
    file.write_text(block + "".join(lines[start:]), encoding="utf-8")


def stale_migration_files(recorded, current):
    """Fitxers de l'abocament que ja no tenen el mateix contingut."""
    if not recorded:
        return []
    return sorted(
        f"{app}.{name}"
        for (app, name), digest in recorded.items()
        if current.get((app, name)) != digest
    )


def migrations_not_in_graph(applied, known_nodes):
    """Migracions aplicades que aquest codi no coneix.

    Un abocament amb migracions desconegudes ve d'una branca més nova. Django
    no les desfà, i desar aquell estat amb la clau d'aquest codi fixaria un
    esquema que no li correspon.
    """
    return sorted(
        f"{app}.{name}"
        for app, name in applied
        if (app, name) not in known_nodes
    )


class Command(BaseCommand):
    help = (
        "Aplica les migracions a una base temporal i escriu un abocament SQL "
        "amb l'estat final, per restaurar-lo a les proves sense tornar a "
        "migrar. Amb --from-dump només aplica les migracions que hi falten. "
        "Només amb customers.settings_test."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            required=True,
            help="Fitxer .sql de sortida, per exemple .ci/test_schema.sql",
        )
        parser.add_argument(
            "--from-dump",
            default="",
            help=(
                "Abocament SQL ja migrat. Es restaura i només s'apliquen les "
                "migracions pendents. Si no encaixa amb aquest codi, es "
                "reconstrueix des de zero."
            ),
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
        from_dump = options["from_dump"]
        started = time.monotonic()
        try:
            self._recreate_build_database()
            self._use_build_database()
            outcome = self._try_reuse(from_dump, options["verbosity"])
            if outcome is None:
                self.stdout.write("Aplicant totes les migracions des de zero...")
                call_command(
                    "migrate",
                    interactive=False,
                    verbosity=options["verbosity"],
                )
                outcome = "scratch"
            connection.close()
            if outcome == "current":
                self._publish_existing_dump(from_dump, output)
                if not read_migration_manifest(output):
                    write_migration_manifest(output, migration_hashes())
                self.stdout.write(
                    "L'esquema previ ja cobreix aquestes migracions "
                    f"({time.monotonic() - started:.0f}s)."
                )
            else:
                self.stdout.write(
                    f"Migracions aplicades en {time.monotonic() - started:.0f}s. "
                    "Escrivint l'abocament..."
                )
                partial = output + ".partial"
                try:
                    try:
                        dump_database(
                            connection.settings_dict, BUILD_DATABASE, partial
                        )
                    except SchemaDumpError as exc:
                        raise CommandError(str(exc)) from exc
                    os.replace(partial, output)
                    write_migration_manifest(output, migration_hashes())
                finally:
                    if os.path.exists(partial):
                        os.remove(partial)
        finally:
            connection.close()
            settings.DATABASES["default"]["NAME"] = original_name
            connection.settings_dict["NAME"] = original_name
            self._drop_build_database()

        self.stdout.write(self.style.SUCCESS(f"Esquema de test escrit a {output}"))

    def _use_build_database(self):
        settings.DATABASES["default"]["NAME"] = BUILD_DATABASE
        connection.settings_dict["NAME"] = BUILD_DATABASE
        connection.close()

    def _try_reuse(self, from_dump, verbosity):
        """Restaura un abocament i aplica el que hi falta.

        Retorna ``current`` si no cal tornar a abocar, ``updated`` si s'han
        aplicat migracions noves, o ``None`` si s'ha de migrar des de zero.
        """
        if not from_dump:
            return None
        path = os.path.abspath(from_dump)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            self.stdout.write("No hi ha un esquema previ per reutilitzar.")
            return None

        try:
            recorded = read_migration_manifest(path)
            if not recorded:
                raise SchemaDumpError(
                    "L'abocament previ no té manifest de migracions."
                )
            current = migration_hashes()
            stale = stale_migration_files(recorded, current)
            if stale:
                sample = ", ".join(stale[:5])
                extra = "" if len(stale) <= 5 else f" i {len(stale) - 5} més"
                raise SchemaDumpError(
                    "Han canviat migracions que l'esquema previ ja tenia "
                    f"aplicades ({sample}{extra})."
                )
            if recorded and set(recorded) == set(current):
                self.stdout.write(
                    "L'esquema en cache ja correspon a aquestes migracions."
                )
                return "current"
            self.stdout.write(
                "Restaurant l'esquema previ i aplicant només les migracions "
                f"que hi falten ({path})..."
            )
            load_sql_file(connection.settings_dict, BUILD_DATABASE, path)
            connection.close()
            executor = MigrationExecutor(connection)
            missing = migrations_not_in_graph(
                executor.loader.applied_migrations,
                executor.loader.graph.nodes,
            )
            if missing:
                sample = ", ".join(missing[:5])
                extra = "" if len(missing) <= 5 else f" i {len(missing) - 5} més"
                raise SchemaDumpError(
                    "L'esquema previ conté migracions que aquest codi no té "
                    f"({sample}{extra})."
                )
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if not plan:
                return "current"
            call_command("migrate", interactive=False, verbosity=verbosity)
            return "updated"
        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(
                    "No es reutilitza l'esquema previ "
                    f"({exc.__class__.__name__}: {exc}). "
                    "Es reconstrueix des de zero."
                )
            )
            self._recreate_build_database()
            self._use_build_database()
            return None

    def _publish_existing_dump(self, from_dump, output):
        source = os.path.abspath(from_dump)
        target = os.path.abspath(output)
        if source == target:
            return
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        shutil.copyfile(source, target)

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
