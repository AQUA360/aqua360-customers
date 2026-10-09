"""
Generació de files CSV per exportació de contractes (acció export/excel).
"""
import csv
from decimal import Decimal
from io import StringIO

from django.db.models import Q
from django.utils.translation import gettext as _

from contract.models import Contract, Variable
from coredata.models import ConfigProject


def _person_label(person):
    if not person:
        return ''
    return f"{person.name or ''} {person.surname or ''}".strip()


def _address_str_from_person_address(person_address):
    if not person_address:
        return ''
    try:
        if person_address.address:
            return str(person_address.address)
    except Exception:
        pass
    return ''


def _supply_point_code(supply_point):
    if not supply_point:
        return ''
    return (supply_point.token or supply_point.name or '').strip()


def _supply_point_address(supply_point):
    if not supply_point:
        return ''
    try:
        if supply_point.address:
            return str(supply_point.address)
    except Exception:
        pass
    return ''


def _route_and_route_position_from_supply_point(supply_point):
    """
    Route / RoutePosition via Property del SupplyPoint:
    supply_point.property.route_position → route / position.
    Retorna (route_label, route_position_label).
    """
    if not supply_point:
        return '', ''
    prop = getattr(supply_point, 'property', None)
    if not prop:
        return '', ''
    rp = getattr(prop, 'route_position', None)
    if not rp:
        return '', ''
    route = getattr(rp, 'route', None)
    route_label = ''
    if route:
        route_label = (route.token or route.name or str(route.id)).strip()
    if rp.position is not None:
        position_label = str(rp.position)
    elif rp.token:
        position_label = str(rp.token).strip()
    else:
        position_label = ''
    return route_label, position_label


def _exploitation_triple_for_supply_point(sp):
    """Explotació via punt de subministrament → connection → exploitation."""
    if not sp:
        return '', '', ''
    try:
        conn = sp.connection
        if not conn:
            return '', '', ''
        expl = conn.exploitation
        if not expl:
            return '', '', ''
        return expl.id, expl.token or '', expl.name or ''
    except Exception:
        return '', '', ''


def _communication_label(value):
    if not value:
        return ''
    mapping = dict(Contract.COMMUNICATION_CHOICES)
    return mapping.get(value, value)


def _payment_type_label(general_payment):
    if not general_payment or not general_payment.type:
        return ''
    pt = general_payment.type
    if (pt.name or '').strip():
        return pt.name.strip()
    if hasattr(pt, 'get_token_display'):
        return pt.get_token_display()
    return ''


def _facturable_label(contract):
    """Contracte facturable quan no té bloqueig de facturació (block_billing)."""
    if getattr(contract, 'block_billing', False):
        return _('No')
    return _('Sí')


def general_payment_personbank_dni(contract):
    """
    PersonBank.dni només del GeneralPayment d'aquest contracte.
    Sense GeneralPayment o sense IBAN (PersonBank) → buit (no s'agafen altres comptes de la persona).
    """
    payment = contract.payment
    if not payment or not payment.IBAN_id:
        return ''
    return (payment.IBAN.dni or '').strip()


def _sepa_person_bank_fields(general_payment):
    """Retorna (iban, name, dni) només si el pagament és SEPA amb IBAN de PersonBank."""
    if not general_payment or not general_payment.type:
        return '', '', ''
    if general_payment.type.token != 'DIRECT_DEBIT':
        return '', '', ''
    iban_row = general_payment.IBAN
    if not iban_row or not (iban_row.iban or '').strip():
        return '', '', ''
    return (
        (iban_row.iban or '').strip(),
        (iban_row.name or '').strip(),
        (iban_row.dni or '').strip(),
    )


def variable_names_used_in_queryset(filtered_contract_qs):
    names = (
        Variable.objects.filter(contract__in=filtered_contract_qs, is_active=True)
        .exclude(Q(name__isnull=True) | Q(name=''))
        .values_list('name', flat=True)
        .distinct()
    )
    return sorted(set(names))


def sanitize_csv_header(text):
    if text is None:
        return ''
    s = str(text).replace(';', ',').replace('\n', ' ').replace('\r', ' ')
    return s.strip()


def debt_amount_by_contract_id(contract_ids):
    """Mateix deute que el llistat i el detall (vw_contract_debt)."""
    from contract.utils.contract_list_queryset import contract_debt_amounts_by_contract_id

    return contract_debt_amounts_by_contract_id(contract_ids)


def prepare_contract_export_queryset(filtered_contract_qs):
    return filtered_contract_qs.select_related(
        'supply_point_default__address__street__type',
        'supply_point_default__address__street_number__number_type',
        'supply_point_default__address__city',
        'supply_point_default__address__country',
        'supply_point_default__connection__exploitation',
        'supply_point_default__property__route_position__route',
        'address_billing__address__street__type',
        'address_billing__address__street_number__number_type',
        'address_billing__address__city',
        'address_billing__address__country',
        'address_contact__address__street__type',
        'address_contact__address__street_number__number_type',
        'address_contact__address__city',
        'address_contact__address__country',
        'payment__type',
        'payment__IBAN',
        'person_contact_email',
        'piggy_bank',
        'holder',
        'owner',
        'tenant',
        'status',
        'use_type',
        'category',
        'client_type',
        'debt_management',
    )


def variables_value_map_by_contract(contract_ids, variable_names):
    """
    Un sol query: valors de Variable per contracte (per nom).
    Si hi ha més d'una variable amb el mateix nom, guanyen la d'id més alt (order_by id).
    """
    if not contract_ids or not variable_names:
        return {}
    qs = (
        Variable.objects.filter(
            contract_id__in=contract_ids,
            is_active=True,
            name__in=list(variable_names),
        )
        .order_by('id')
    )
    by_contract = {}
    for v in qs:
        if not v.name:
            continue
        by_contract.setdefault(v.contract_id, {})[v.name] = (v.value or '').strip()
    return by_contract


def build_contract_export_headers(variable_names):
    base = [
        _('Token'),
        _('Titular'),
        _('Titular token'),
        _('Document PersonBank.dni (GeneralPayment)'),
        _('Propietari'),
        _('Propietari token'),
        _('Inquilí'),
        _('Inquilí token'),
        _('Estat'),
        _('Ús'),
        _('Categoria'),
        _('Tipus client'),
        _('Gestió del deute'),
        _('ID explotació'),
        _('Token explotació'),
        _('Nom explotació'),
        _('Punt subministrament (codi)'),
        _('Punt subministrament (adreça)'),
        _('Route'),
        _('RoutePosition'),
        _('Adreça fiscal'),
        _('Adreça contacte'),
        _('Comunicació'),
        _('E-mail comunicació'),
        _('Tipus de pagament'),
        _('PersonBank IBAN (SEPA)'),
        _('PersonBank titular (SEPA)'),
        _('PersonBank DNI (SEPA)'),
        _('Facturable'),
        _('Saldo contracte'),
        _('Deute contracte'),
        _('Nombre persones habitatge'),
        _('Data creació'),
    ]
    var_headers = [sanitize_csv_header(n) for n in variable_names]
    return base + var_headers


def contract_row_values(contract, variable_names, debt_map, variables_by_contract):
    sp = contract.supply_point_default
    expl_id, expl_token, expl_name = _exploitation_triple_for_supply_point(sp)
    route_label, route_position_label = _route_and_route_position_from_supply_point(sp)
    comm = contract.communication_type or ''
    email_comm = ''
    if comm == 'DIGITAL' and contract.person_contact_email:
        email_comm = (contract.person_contact_email.email or '').strip()

    iban, pb_name, pb_dni = _sepa_person_bank_fields(contract.payment)
    saldo = contract.piggy_bank.amount if contract.piggy_bank else Decimal('0')
    deute = debt_map.get(contract.id, Decimal('0'))

    var_by_name = variables_by_contract.get(contract.id, {})

    row = [
        contract.token or '',
        _person_label(contract.holder),
        contract.holder.token if contract.holder else '',
        general_payment_personbank_dni(contract),
        _person_label(contract.owner),
        contract.owner.token if contract.owner else '',
        _person_label(contract.tenant),
        contract.tenant.token if contract.tenant else '',
        contract.status.name if contract.status else '',
        contract.use_type.name if contract.use_type else '',
        contract.category.name if contract.category else '',
        contract.client_type.name if contract.client_type else '',
        contract.debt_management.name if contract.debt_management else '',
        expl_id,
        expl_token,
        expl_name,
        _supply_point_code(sp),
        _supply_point_address(sp),
        route_label,
        route_position_label,
        _address_str_from_person_address(contract.address_billing),
        _address_str_from_person_address(contract.address_contact),
        _communication_label(comm),
        email_comm,
        _payment_type_label(contract.payment),
        iban,
        pb_name,
        pb_dni,
        _facturable_label(contract),
        str(saldo).replace('.', ','),
        str(deute).replace('.', ','),
        contract.total_persons if contract.total_persons is not None else '',
        contract.created_at.strftime('%d/%m/%Y') if contract.created_at else '',
    ]
    row.extend(var_by_name.get(name, '') for name in variable_names)
    return row


def build_contract_export_csv_bytes(filtered_queryset):
    """
    CSV complet (UTF-8 amb BOM) a partir d'un queryset de Contract ja filtrat.
    Compartit per la vista síncrona i per l'informe Celery de statistics.
    """
    variable_names = variable_names_used_in_queryset(filtered_queryset)
    export_qs = prepare_contract_export_queryset(filtered_queryset)
    contract_ids = list(export_qs.values_list('pk', flat=True))
    debt_map = debt_amount_by_contract_id(contract_ids)
    variables_by_contract = variables_value_map_by_contract(contract_ids, variable_names)

    buffer = StringIO()
    buffer.write('\ufeff')
    writer = csv.writer(buffer, delimiter=';')
    writer.writerow(build_contract_export_headers(variable_names))
    for contract in export_qs.iterator(chunk_size=500):
        writer.writerow(
            contract_row_values(contract, variable_names, debt_map, variables_by_contract)
        )
    return buffer.getvalue().encode('utf-8')
