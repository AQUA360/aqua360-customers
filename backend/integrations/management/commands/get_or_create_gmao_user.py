from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from decouple import config


class Command(BaseCommand):
    help = "Get or create GMAO inbound user and assign to gmao group"

    def handle(self, *args, **kwargs):
        self.stdout.write("⚙️  Setting GMAO user up...")

        gmao_group, group_created = Group.objects.get_or_create(name="gmao")
        self._notify(group_created, "GMAO group")

        User = get_user_model()
        username = config("GMAO_USER_USERNAME")
        password = config("GMAO_USER_PASSWORD")
        email = config("GMAO_USER_EMAIL")

        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        if user_created:
            user.set_password(password)
            user.is_superuser = False
            user.is_staff = False
            user.save()
        self._notify(user_created, "GMAO user")

        if not user.groups.filter(name="gmao").exists():
            user.groups.add(gmao_group)
            self.stdout.write(self.style.SUCCESS("✅ GMAO user added to gmao group"))

        self.stdout.write(self.style.SUCCESS("🎉 GMAO user setup complete!"))

        token, token_created = Token.objects.get_or_create(user=user)
        self._notify(token_created, "Token")
        self.stdout.write(self.style.SUCCESS(f"🔑 Token: {token.key}"))

    def _notify(self, created: bool, item: str):
        if created:
            self.stdout.write(self.style.SUCCESS(f"✨ {item} created"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ {item} already exists"))
