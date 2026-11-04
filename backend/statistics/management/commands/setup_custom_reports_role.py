"""Crea o actualitza el rol de PostgreSQL de només lectura dels informes personalitzats.

    python manage.py setup_custom_reports_role [--role R] [--password P] [--exclude-table T ...]

Per defecte agafa el rol i la contrasenya de CUSTOM_REPORTS_DATABASE_USER/_PASSWORD. Dona SELECT
sobre totes les taules i vistes de l'esquema actual excepte les sensibles (tokens, sessions,
contrasenyes), que queden sense accés o amb accés per columnes. És idempotent: tornar-lo a
executar després d'una actualització per donar accés a les taules noves.
Cal executar-lo amb un usuari de BD que pugui crear rols (CREATEROLE) i donar permisos.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from statistics.utils.custom_report_service import (
    EXCLUDED_TABLE_PREFIXES,
    EXCLUDED_TABLES,
    SENSITIVE_COLUMNS,
)


class Command(BaseCommand):
    help = "Crea/actualitza el rol de PostgreSQL de només lectura per als informes personalitzats."

    def add_arguments(self, parser):
        parser.add_argument("--role", default=settings.CUSTOM_REPORTS_DATABASE_USER)
        parser.add_argument("--password", default=settings.CUSTOM_REPORTS_DATABASE_PASSWORD)
        parser.add_argument(
            "--exclude-table", action="append", default=[],
            help="Taula addicional sense accés (es pot repetir).",
        )

    def handle(self, *args, **options):
        role = (options["role"] or "").strip()
        password = options["password"] or ""
        if not role:
            raise CommandError("Indica el rol amb --role o CUSTOM_REPORTS_DATABASE_USER.")
        if role == settings.DATABASES["default"]["USER"]:
            raise CommandError("El rol d'informes no pot ser el mateix usuari que l'aplicació.")
        excluded = set(EXCLUDED_TABLES) | set(options["exclude_table"])
        q = connection.ops.quote_name
        timeout = f"{int(settings.CUSTOM_REPORTS_STATEMENT_TIMEOUT)}s"

        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
            exists = cursor.fetchone() is not None
            if not exists:
                if not password:
                    raise CommandError("Cal una contrasenya per crear el rol (--password).")
                cursor.execute(f"CREATE ROLE {q(role)} LOGIN PASSWORD %s", [password])
                self.stdout.write(f"Rol creat: {role}")
            elif password:
                cursor.execute(f"ALTER ROLE {q(role)} WITH LOGIN PASSWORD %s", [password])
            cursor.execute(f"ALTER ROLE {q(role)} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION")
            cursor.execute(f"ALTER ROLE {q(role)} SET default_transaction_read_only = on")
            cursor.execute(f"ALTER ROLE {q(role)} SET statement_timeout = %s", [timeout])

            cursor.execute("SELECT current_database(), current_schema()")
            database, schema = cursor.fetchone()
            cursor.execute(f"GRANT CONNECT ON DATABASE {q(database)} TO {q(role)}")
            cursor.execute(f"GRANT USAGE ON SCHEMA {q(schema)} TO {q(role)}")
            # Es parteix de zero (també revoca els permisos per columna) i es tornen a donar.
            cursor.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {q(schema)} FROM {q(role)}")
            cursor.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {q(schema)} FROM {q(role)}")

            cursor.execute(
                """
                SELECT c.relname
                FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relkind IN ('r', 'v', 'm', 'p', 'f')
                ORDER BY c.relname
                """,
                [schema],
            )
            tables = [r[0] for r in cursor.fetchall()]
            granted = partial = skipped = 0
            for table in tables:
                if table in excluded or table.startswith(EXCLUDED_TABLE_PREFIXES):
                    skipped += 1
                    continue
                hidden = SENSITIVE_COLUMNS.get(table)
                if hidden:
                    cursor.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                        [schema, table],
                    )
                    columns = [r[0] for r in cursor.fetchall() if r[0] not in hidden]
                    if columns:
                        cols = ", ".join(q(c) for c in columns)
                        cursor.execute(f"GRANT SELECT ({cols}) ON {q(schema)}.{q(table)} TO {q(role)}")
                    partial += 1
                    continue
                cursor.execute(f"GRANT SELECT ON {q(schema)}.{q(table)} TO {q(role)}")
                granted += 1

        self.stdout.write(self.style.SUCCESS(
            f"Rol '{role}' preparat: {granted} taules/vistes amb lectura, {partial} amb columnes "
            f"restringides, {skipped} sense accés. Configura CUSTOM_REPORTS_DATABASE_USER/_PASSWORD "
            "al .env i reinicia el backend."
        ))
