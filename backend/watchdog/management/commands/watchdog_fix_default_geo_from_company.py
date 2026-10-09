from django.core.management.base import BaseCommand
from django.db import transaction

from coredata.models import City, Country, Province
from service.models import Company


class Command(BaseCommand):
    help = (
        "Marca com a is_default el Country, Province i City de l'adreça de la primera "
        "Company (id ASC). Ús després del watchdog si falta algun per defecte."
    )

    def _set_default(self, model, pk, label):
        if pk is None:
            self.stdout.write(
                self.style.WARNING(
                    f"L'adreça de la Company no té {label}; no s'ha pogut assignar per defecte."
                )
            )
            return False
        if not model.objects.filter(pk=pk).exists():
            self.stdout.write(
                self.style.ERROR(f"No existeix {label} amb id={pk}.")
            )
            return False
        model.objects.update(is_default=False)
        updated = model.objects.filter(pk=pk).update(is_default=True)
        instance = model.objects.get(pk=pk)
        self.stdout.write(
            self.style.SUCCESS(
                f"{model.__name__} id={pk} ({instance}) marcat com a is_default."
            )
        )
        return updated > 0

    def handle(self, *args, **options):
        company = Company.objects.select_related("address").order_by("id").first()
        if not company:
            self.stdout.write(
                self.style.ERROR("No hi ha cap Company a la base de dades.")
            )
            return

        address = company.address
        if not address:
            self.stdout.write(
                self.style.ERROR(
                    f"La Company id={company.id} no té adreça (address_id buit)."
                )
            )
            return

        self.stdout.write(
            f"Company id={company.id}, Address id={address.id}: "
            f"country_id={address.country_id}, province_id={address.province_id}, "
            f"city_id={address.city_id}"
        )

        with transaction.atomic():
            ok_country = self._set_default(Country, address.country_id, "country_id")
            ok_province = self._set_default(Province, address.province_id, "province_id")
            ok_city = self._set_default(City, address.city_id, "city_id")

        if ok_country and ok_province and ok_city:
            self.stdout.write(self.style.SUCCESS("Valors per defecte assignats correctament."))
        elif not (ok_country or ok_province or ok_city):
            self.stdout.write(
                self.style.ERROR(
                    "No s'ha pogut assignar cap valor per defecte; revisa l'adreça de la Company."
                )
            )
