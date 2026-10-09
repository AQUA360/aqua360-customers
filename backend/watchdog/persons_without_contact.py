from collections import defaultdict

from django.db.models import Exists, OuterRef, Q

from billing.models import GeneralPayment, Invoice, PaymentCommitment
from contract.models import Contract, ContractDataChange, ContractPayment, ContractRepresentative
from coredata.models import ConfigProject, Person, PersonAddress, PersonBank, PersonContact

ZOMBIE_PERSONS_CHECK_NAME = "Persones sense contacte ni adreça ni cap contracte"
ACTIVE_CONTRACT_CHECK_NAME = "Persones sense contacte ni adreça amb contracte actiu"
WARNING_CHECK_NAMES = frozenset({ACTIVE_CONTRACT_CHECK_NAME})

ACTIVE_CONTRACT_CONFIG_TOKEN = "contract_active_token"

WATCHDOG_FIX_DELETE_ZOMBIE_PERSONS_COMMAND = (
    "python manage.py watchdog_fix_delete_zombie_persons --dry-run\n"
    "  python manage.py watchdog_fix_delete_zombie_persons"
)

_CONTRACT_ROLES = (
    ("titular", "holder_id"),
    ("propietari", "owner_id"),
    ("llogater", "tenant_id"),
)


def get_persons_without_contact_nor_address_queryset():
    return Person.objects.filter(
        ~Exists(PersonContact.objects.filter(person_id=OuterRef("pk"))),
        ~Exists(PersonAddress.objects.filter(person_id=OuterRef("pk"))),
    )


def _has_any_contract():
    return (
        Exists(Contract.objects.filter(holder_id=OuterRef("pk")))
        | Exists(Contract.objects.filter(owner_id=OuterRef("pk")))
        | Exists(Contract.objects.filter(tenant_id=OuterRef("pk")))
        | Exists(
            ContractRepresentative.objects.filter(
                person_id=OuterRef("pk"),
                contract__isnull=False,
            )
        )
    )


def get_zombie_persons_queryset():
    """Persones sense contacte, ni adreça, ni cap contracte (titular, propietari, llogater o representant)."""
    return (
        get_persons_without_contact_nor_address_queryset()
        .filter(~_has_any_contract())
        .order_by("id")
    )


def format_person_label(person):
    name = f"{person.name or ''} {person.surname or ''}".strip() or "Sense nom"
    token = person.token or "sense token"
    return f"Persona ID {person.id} ({name}, {token})"


def format_zombie_person_issue(person):
    return (
        f"{format_person_label(person)} no té contacte, ni adreça, ni cap contracte"
    )


def check_zombie_person_issues():
    zombies = get_zombie_persons_queryset()
    total = zombies.count()
    if total == 0:
        return []

    issues = [
        f"S'han trobat {total} persones sense contacte, ni adreça, ni cap contracte "
        "(titular, propietari, llogater o representant)"
    ]
    max_display = 50
    for person in zombies[:max_display]:
        issues.append(format_zombie_person_issue(person))
    if total > max_display:
        issues.append(f"... i {total - max_display} persones més (total: {total})")

    issues.append("")
    issues.append("Recomanació (watchdog): elimina les persones zombi amb:")
    for line in WATCHDOG_FIX_DELETE_ZOMBIE_PERSONS_COMMAND.splitlines():
        issues.append(f"  {line}")
    return issues


def _active_contract_token():
    return ConfigProject.objects.get(token=ACTIVE_CONTRACT_CONFIG_TOKEN).value


def _add_contract_link(links, person_id, role, token, allowed_ids):
    if person_id not in allowed_ids:
        return
    label = token or "sense token"
    roles = links[person_id].setdefault(label, [])
    if role not in roles:
        roles.append(role)


def get_persons_with_active_contract():
    """
    Persones sense contacte ni adreça que són titular, propietari, llogater
    o representant d'un contracte amb l'estat actiu (ConfigProject contract_active_token).

    Retorna una llista de (person, {token: [rols]}).
    """
    active_token = _active_contract_token()
    allowed_ids = set(
        get_persons_without_contact_nor_address_queryset().values_list("pk", flat=True)
    )
    if not allowed_ids:
        return []

    links = defaultdict(dict)
    role_query = Q()
    for _role, field in _CONTRACT_ROLES:
        role_query |= Q(**{f"{field}__in": allowed_ids})

        contracts = Contract.objects.filter(status__token=active_token).filter(role_query).only(
        "id", "token", "holder_id", "owner_id", "tenant_id"
    )
    for contract in contracts:
        label = contract.token or f"#{contract.id}"
        for role, field in _CONTRACT_ROLES:
            _add_contract_link(
                links,
                getattr(contract, field),
                role,
                label,
                allowed_ids,
            )

    representatives = ContractRepresentative.objects.filter(
        person_id__in=allowed_ids,
        contract__isnull=False,
        contract__status__token=active_token,
    ).select_related("contract")
    for representative in representatives:
        _add_contract_link(
            links,
            representative.person_id,
            "representant",
            representative.contract.token or f"#{representative.contract_id}",
            allowed_ids,
        )

    if not links:
        return []

    persons = Person.objects.filter(id__in=links).order_by("id")
    return [(person, links[person.id]) for person in persons]


def format_active_contract_person_issue(person, contracts_by_token):
    parts = [
        f"{token} ({', '.join(roles)})"
        for token, roles in contracts_by_token.items()
    ]
    contracts_label = ", ".join(parts)
    return (
        f"{format_person_label(person)} no té contacte ni adreça i té contracte actiu: "
        f"{contracts_label}. Cal entrar al contracte i sanejar-ho a mà."
    )


def check_active_contract_person_issues():
    try:
        rows = get_persons_with_active_contract()
    except ConfigProject.DoesNotExist:
        return [
            "Error de configuració: no existeix ConfigProject «contract_active_token»"
        ]

    total = len(rows)
    if total == 0:
        return []

    issues = [
        f"S'han trobat {total} persones sense contacte ni adreça amb un contracte actiu. "
        "Cal entrar al contracte i sanejar-ho a mà."
    ]
    max_display = 50
    for person, contracts_by_token in rows[:max_display]:
        issues.append(format_active_contract_person_issue(person, contracts_by_token))
    if total > max_display:
        issues.append(f"... i {total - max_display} persones més (total: {total})")
    return issues


def person_ids_with_bank_in_use(person_ids):
    """
    Persones el PersonBank de les quals el fa servir un contracte, una factura,
    un pagament general, un compromís o un canvi de dades. Esborrar la persona
    esborraria el compte en cascada i deixaria aquests registres sense IBAN.
    """
    if not person_ids:
        return set()

    banks = PersonBank.objects.filter(person_id__in=person_ids)
    sources = [
        ContractPayment.objects.filter(IBAN__in=banks).values_list("IBAN__person_id", flat=True),
        GeneralPayment.objects.filter(IBAN__in=banks).values_list("IBAN__person_id", flat=True),
        Invoice.objects.filter(payment_bank__in=banks).values_list(
            "payment_bank__person_id", flat=True
        ),
        PaymentCommitment.objects.filter(payment_bank__in=banks).values_list(
            "payment_bank__person_id", flat=True
        ),
        ContractDataChange.objects.filter(new_payment__in=banks).values_list(
            "new_payment__person_id", flat=True
        ),
        ContractDataChange.objects.filter(previous_payment__in=banks).values_list(
            "previous_payment__person_id", flat=True
        ),
    ]
    in_use = set()
    for source in sources:
        in_use.update(person_id for person_id in source if person_id)
    return in_use
