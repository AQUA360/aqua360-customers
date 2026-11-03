from django.db.backends.postgresql.base import DatabaseWrapper as PostgresDatabaseWrapper

from .creation import TestSchemaDatabaseCreation


class DatabaseWrapper(PostgresDatabaseWrapper):
    creation_class = TestSchemaDatabaseCreation
