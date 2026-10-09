from .settings import *
from decouple import config

DEBUG = False

DATABASES["default"] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DATABASE_NAME_TEST', default='test_db'),
        'USER': config('DATABASE_USER', default='user_test'),
        'PASSWORD': config('DATABASE_PASSWORD', default='password_test'),
        'HOST': config('DATABASE_HOST', default='localhost'),
        'PORT': config('DATABASE_PORT', cast=int, default=5432),
    }