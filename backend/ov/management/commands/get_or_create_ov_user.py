from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from decouple import config


class Command(BaseCommand):
    help = "Get or create OV user and assign to OV group"

    def handle(self, *args, **kwargs):
        self.stdout.write("⚙️  Setting OV user up...")

        # --- Ensure OV group exists ---
        ov_group, group_created = Group.objects.get_or_create(name="ov")
        self._notify(group_created, "OV group")

        # --- Get or create OV user ---
        User = get_user_model()
        username = config("OV_USER_USERNAME")
        password = config("OV_USER_PASSWORD")
        email = config("OV_USER_EMAIL")

        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        if user_created:
            user.set_password(password)
            user.is_superuser = False
            user.is_staff = False
            user.save()
        self._notify(user_created, "OV user")

        # --- Ensure user is in OV group ---
        if not user.groups.filter(name="ov").exists():
            user.groups.add(ov_group)
            self.stdout.write(self.style.SUCCESS("✅ OV user added to OV group"))

        self.stdout.write(self.style.SUCCESS("🎉 OV user setup complete!"))

        # --- Generate API token ---
        token, token_created = Token.objects.get_or_create(user=user)
        self._notify(token_created, "Token")
        self.stdout.write(self.style.SUCCESS(f"🔑 Token: {token.key}"))


    def _notify(self, created: bool, item: str):
        if created:
            self.stdout.write(self.style.SUCCESS(f"✨ {item} created"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ {item} already exists"))
