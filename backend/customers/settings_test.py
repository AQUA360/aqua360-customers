from .settings import *
from decouple import config

DEBUG = False

# Mateix PostgreSQL de sempre. Si TEST_SCHEMA_FILE apunta a un .sql ja migrat,
# customers.test_db el restaura i es salta l'històric de migracions.
DATABASES["default"] = {
        'ENGINE': 'customers.test_db',
        'NAME': config('DATABASE_NAME_TEST', default='test_db'),
        'USER': config('DATABASE_USER', default='user_test'),
        'PASSWORD': config('DATABASE_PASSWORD', default='password_test'),
        'HOST': config('DATABASE_HOST', default='localhost'),
        'PORT': config('DATABASE_PORT', cast=int, default=5432),
    }