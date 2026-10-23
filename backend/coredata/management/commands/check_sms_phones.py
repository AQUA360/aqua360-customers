from django.core.management.base import BaseCommand

from contract.models import Contract
from coredata.models import PersonContact
from coredata.utils.phone_utils import is_mobile_phone, normalize_phone


class Command(BaseCommand):
    help = (
        "Llista els telèfons que no poden rebre SMS: els triats com a telèfon SMS "
        "d'un contracte actiu que no són mòbils (fixos o mal formats) i, amb "
        "--all-contacts, tots els contactes actius amb telèfon no mòbil. Només "
        "informa: no modifica cap dada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--all-contacts', action='store_true',
            help="Revisa tots els contactes actius, no només els telèfons SMS dels contractes.",
        )

    def handle(self, *args, **options):
        contracts = (
            Contract.objects.filter(is_active=True, person_contact_sms__isnull=False)
            .prefetch_related('person_contact_sms')
            .distinct()
            .order_by('id')
        )
        wrong_links = 0
        contracts_without_mobile = 0
        for contract in contracts:
            phones = [c for c in contract.person_contact_sms.all() if c.is_active and c.phone]
            wrong = [c for c in phones if not is_mobile_phone(c.phone)]
            if not wrong:
                continue
            wrong_links += len(wrong)
            if len(wrong) == len(phones):
                contracts_without_mobile += 1
            for contact in wrong:
                self.stdout.write(
                    f"contract={contract.token} contact_id={contact.id} "
                    f"phone={contact.phone!r} normalized={normalize_phone(contact.phone)!r}"
                )
        self.stdout.write(self.style.WARNING(
            f"{wrong_links} telèfons SMS de contractes no són mòbils; "
            f"{contracts_without_mobile} contractes no tenen cap mòbil per a SMS."
        ))

        if options['all_contacts']:
            wrong_contacts = 0
            contacts = (
                PersonContact.objects.filter(is_active=True, phone__isnull=False)
                .exclude(phone='')
                .order_by('id')
            )
            for contact in contacts.iterator():
                if not is_mobile_phone(contact.phone):
                    wrong_contacts += 1
            self.stdout.write(self.style.WARNING(
                f"{wrong_contacts} de {contacts.count()} contactes actius amb telèfon no són mòbils."
            ))
