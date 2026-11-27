from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decouple import config
from rest_framework.authtoken.models import Token

from integrations.inbound.gmao.permissions import GMAO_GROUP
from ov.middleware import RestrictOVUserMiddleware


class Command(BaseCommand):
    help = "Get or create GMAO inbound user and assign to gmao group"

    def add_arguments(self, parser):
        parser.add_argument(
            "--show-token",
            action="store_true",
            help="Mostra el token sencer (per defecte només se'n veu el final).",
        )

    def handle(self, *args, **options):
        self.stdout.write("⚙️  Setting GMAO user up...")

        User = get_user_model()
        username = config("GMAO_USER_USERNAME")

        with transaction.atomic():
            gmao_group, group_created = Group.objects.get_or_create(name=GMAO_GROUP)
            self._notify(group_created, "GMAO group")

            user = User.objects.filter(username=username).first()
            user_created = user is None
            if user_created:
                # La contrasenya només cal en crear l'usuari; després es pot treure del .env
                user = User(
                    username=username,
                    email=config("GMAO_USER_EMAIL"),
                    is_superuser=False,
                    is_staff=False,
                )
                user.set_password(config("GMAO_USER_PASSWORD"))
                user.save()
            else:
                self._check_reusable(user)
            self._notify(user_created, "GMAO user")

            if not user.groups.filter(name=GMAO_GROUP).exists():
                user.groups.add(gmao_group)
                self.stdout.write(self.style.SUCCESS("✅ GMAO user added to gmao group"))

            token, token_created = Token.objects.get_or_create(user=user)

        self.stdout.write(self.style.SUCCESS("🎉 GMAO user setup complete!"))
        self._notify(token_created, "Token")
        if options.get("show_token"):
            self.stdout.write(self.style.SUCCESS(f"🔑 Token: {token.key}"))
        else:
            # El token no es deixa als registres de Docker o de la CI: només se'n mostra el final.
            self.stdout.write(
                self.style.SUCCESS(
                    f"🔑 Token: ****{token.key[-4:]} (executa l'ordre amb --show-token per veure'l sencer)"
                )
            )

    def _check_reusable(self, user):
        """Un usuari existent només es reaprofita si pot quedar limitat a /gmao/.

        Un administrador perdria l'accés a la resta de l'API, i un usuari d'un altre
        grup restringit (ov, giswater...) quedaria limitat a les rutes d'aquell grup.
        """
        if user.is_superuser or user.is_staff:
            raise CommandError(
                f"User '{user.username}' is an administrator; use a dedicated GMAO user."
            )
        other_groups = set(
            user.groups.filter(name__in=RestrictOVUserMiddleware.RESTRICTED_GROUPS)
            .exclude(name=GMAO_GROUP)
            .values_list("name", flat=True)
        )
        if other_groups:
            raise CommandError(
                f"User '{user.username}' already belongs to restricted group(s) "
                f"{', '.join(sorted(other_groups))}; use a dedicated GMAO user."
            )

    def _notify(self, created: bool, item: str):
        if created:
            self.stdout.write(self.style.SUCCESS(f"✨ {item} created"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ {item} already exists"))
