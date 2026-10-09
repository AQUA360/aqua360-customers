"""Queryset optimitzat per carregar el formulari de modificació de dades del contracte."""
from django.db.models import Prefetch

from contract.models import Contract
from coredata.models import PersonAddress, PersonBank, PersonContact


def contract_data_change_queryset():
    address_qs = PersonAddress.objects.select_related('address').order_by('id')
    bank_qs = PersonBank.objects.all()
    contact_qs = PersonContact.objects.all()

    def person_prefetches(prefix):
        return [
            Prefetch(f'{prefix}__addresses', queryset=address_qs),
            Prefetch(f'{prefix}__banks', queryset=bank_qs),
            Prefetch(f'{prefix}__contacts', queryset=contact_qs),
        ]

    return Contract.objects.select_related(
        'holder',
        'owner',
        'tenant',
        'supply_point_default',
        'address_billing',
        'address_billing__address',
        'address_contact',
        'address_contact__address',
        'person_contact_email',
        'payment',
        'payment__type',
        'payment__IBAN',
        'payment__sepa_document',
    ).prefetch_related(
        'contacts',
        'person_contact_sms',
        'representatives',
        'representatives__type',
        *person_prefetches('holder'),
        *person_prefetches('owner'),
        *person_prefetches('tenant'),
        Prefetch('representatives__person__addresses', queryset=address_qs),
        Prefetch('representatives__person__banks', queryset=bank_qs),
        Prefetch('representatives__person__contacts', queryset=contact_qs),
    )
