from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from decouple import config


class Command(BaseCommand):
    help = "Get or create Giswater inbound user and assign to giswater group"

    def handle(self, *args, **kwargs):
        self.stdout.write("⚙️  Setting Giswater user up...")

        giswater_group, group_created = Group.objects.get_or_create(name="giswater")
        self._notify(group_created, "Giswater group")

        User = get_user_model()
        username = config("GISWATER_USER_USERNAME")
        password = config("GISWATER_USER_PASSWORD")
        email = config("GISWATER_USER_EMAIL")

        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        if user_created:
            user.set_password(password)
            user.is_superuser = False
            user.is_staff = False
            user.save()
        self._notify(user_created, "Giswater user")

        if not user.groups.filter(name="giswater").exists():
            user.groups.add(giswater_group)
            self.stdout.write(self.style.SUCCESS("✅ Giswater user added to giswater group"))

        self.stdout.write(self.style.SUCCESS("🎉 Giswater user setup complete!"))

        token, token_created = Token.objects.get_or_create(user=user)
        self._notify(token_created, "Token")
        self.stdout.write(self.style.SUCCESS(f"🔑 Token: {token.key}"))

    def _notify(self, created: bool, item: str):
        if created:
            self.stdout.write(self.style.SUCCESS(f"✨ {item} created"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ {item} already exists"))
