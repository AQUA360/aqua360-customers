from django.core.management.base import BaseCommand
from django.db import transaction

from coredata.models import ConfigProject
from service.models import Company


class Command(BaseCommand):
    help = (
        "Assigna el valor de ConfigProject 'main_company_token' al NIF (Company.vat) "
        "de la primera Company ordenada per id ASC (ús després del watchdog si falla la comprovació)."
    )

    def handle(self, *args, **options):
        company = Company.objects.order_by("id").first()
        if not company:
            self.stdout.write(
                self.style.ERROR("No hi ha cap Company a la base de dades.")
            )
            return

        try:
            config = ConfigProject.objects.get(token="main_company_token")
        except ConfigProject.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    "No existeix ConfigProject amb token 'main_company_token'."
                )
            )
            return

        new_value = company.vat
        if not new_value:
            self.stdout.write(
                self.style.WARNING(
                    f"La Company amb id mínim ({company.id}) té Company.vat buit; "
                    "s'assignarà valor buit al ConfigProject."
                )
            )

        old_value = config.value
        with transaction.atomic():
            config.value = new_value
            config.save(update_fields=["value"])

        self.stdout.write(
            self.style.SUCCESS(
                f"ConfigProject 'main_company_token' actualitzat: "
                f"{old_value!r} -> {new_value!r} (Company id={company.id})."
            )
        )
