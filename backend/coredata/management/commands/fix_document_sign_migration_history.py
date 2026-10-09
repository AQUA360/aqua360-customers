from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = (
        "Idempotent fix for servers where coredata.0114_update_contract_keeper_use_type_name "
        "was applied before its dependency coredata.0113_add_document_sign_enabled_config "
        "was ever recorded, which blocks 'migrate' with InconsistentMigrationHistory."
    )

    def handle(self, *args, **options):
        recorder = MigrationRecorder(connection)
        if not recorder.has_table():
            return

        applied = recorder.applied_migrations()
        migration_113 = ("coredata", "0113_add_document_sign_enabled_config")
        migration_114 = ("coredata", "0114_update_contract_keeper_use_type_name")

        if migration_113 in applied or migration_114 not in applied:
            return

        self.stdout.write(self.style.WARNING(
            "Detected coredata.0114 applied without coredata.0113 recorded. Fixing..."
        ))

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM coredata_configproject WHERE token = %s",
                ["DOCUMENT_SIGN_ENABLED"],
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    """
                    INSERT INTO coredata_configproject
                        (created_at, updated_at, token, name, value, file)
                    VALUES (now(), now(), %s, %s, %s, %s)
                    """,
                    [
                        "DOCUMENT_SIGN_ENABLED",
                        "Signatura de documents (OTP) habilitada",
                        "false",
                        "General",
                    ],
                )
                self.stdout.write(self.style.SUCCESS(
                    "Created missing ConfigProject row for DOCUMENT_SIGN_ENABLED."
                ))

            cursor.execute(
                "SELECT applied FROM django_migrations WHERE app = %s AND name = %s",
                list(migration_114),
            )
            row = cursor.fetchone()
            applied_114 = row[0]

        recorder.migration_qs.create(
            app=migration_113[0],
            name=migration_113[1],
            applied=applied_114 - timedelta(seconds=1),
        )
        self.stdout.write(self.style.SUCCESS(
            "Recorded coredata.0113_add_document_sign_enabled_config as applied."
        ))
