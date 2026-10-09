# coredata/management/commands/create_superuser_and_token.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.authtoken.models import Token
import os

class Command(BaseCommand):
    help = 'Crea un superusuari i genera un token d\'autenticació si no existeixen.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Nom d\'usuari per al superusuari (opcional, per defecte utilitza la variable d\'entorn staging_user)',
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Contrasenya per al superusuari (opcional, per defecte utilitza la variable d\'entorn staging_passwd)',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options.get('username') or os.getenv('staging_user', 'customers')
        # Utilitza el paràmetre --password si es proporciona, sinó utilitza la variable d'entorn
        password = options.get('password') or os.getenv('staging_passwd', 'customers')
        email = os.getenv('staging_email', 'customers@aventec.cat')  # Opcional: pots definir una variable d'entorn per l'email

        user, created = User.objects.get_or_create(username=username, defaults={'email': email})
        
        if created:
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Superusuari "{username}" creat correctament.'))
        else:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.WARNING(f'El superusuari "{username}" ja existeix.'))

        # Crear o obtenir el token
        token, token_created = Token.objects.get_or_create(user=user)
        if token_created:
            self.stdout.write(self.style.SUCCESS(f'Token creat: {token.key}'))
        else:
            self.stdout.write(self.style.WARNING(f'Token ja existeix per l\'usuari "{username}".'))
