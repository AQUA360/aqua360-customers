from django.db.models import Exists, OuterRef

from coredata.models import Address, PersonAddress
from order.models import Order
from service.models import Company, SupplyPoint

WATCHDOG_FIX_ORPHANED_ADDRESSES_COMMAND = (
    "python manage.py watchdog_fix_orphaned_addresses --dry-run\n"
    "  python manage.py watchdog_fix_orphaned_addresses"
)


def get_orphaned_addresses_queryset():
    return Address.objects.filter(
        ~Exists(PersonAddress.objects.filter(address=OuterRef('pk'))),
        ~Exists(SupplyPoint.objects.filter(address=OuterRef('pk'))),
        ~Exists(Order.objects.filter(address=OuterRef('pk'))),
        ~Exists(Company.objects.filter(address=OuterRef('pk'))),
    ).order_by('id')


def format_orphaned_address_issue(address):
    label = str(address).strip() or address.address_search or address.token or 'Sense descripció'
    return f"Address ID {address.id} ({label})"
