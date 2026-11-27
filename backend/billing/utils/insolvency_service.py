"""Procés d'insolvència d'una persona (#2633).

- En crear-lo s'activa l'anomalia «Insolvent» de la persona (o es reutilitza la vigent).
- Hi entren totes les factures emeses des de la data d'insolvència; segueixen la facturació normal.
- Els contractes on la persona és titular passen a la gestió d'impagats «Insolvent», i des del
  procés se'n pot canviar la forma de pagament.
- Mentre és obert, la persona no entra a les reclamacions de deute ni se li pot activar un tall
  indefinit; la facturació i la generació de remeses n'avisen.
- En tancar-lo es torna la gestió d'impagats d'abans i, si es demana, la forma de pagament.
  Després, el deute es pot tornar a reclamar.
"""
import uuid

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from coredata.models import ConfigProject, PersonAnomaly, PersonAnomalyType


INSOLVENT_ANOMALY_TOKEN = 'insolvent'
INSOLVENT_DEBT_MANAGEMENT_TOKEN = 'insolvent'


# Missatges per a l'usuari, per codi: la resposta de l'API mai no porta el text de l'excepció
ERROR_MESSAGES = {
    'invalid_person': 'Persona no vàlida.',
    'invalid_date': 'Data no vàlida.',
    'invalid_kind': 'Tipus de procés no vàlid.',
    'already_open': "La persona ja té un procés d'insolvència obert.",
    'missing_anomaly_type': "No hi ha el tipus d'anomalia «Insolvent».",
    'invalid_ids': 'Identificadors no vàlids.',
    'invalid_payment_changes': 'Canvis de forma de pagament no vàlids.',
    'invalid_contract': 'Algun contracte no és de la persona.',
    'invalid_payment_type': 'Forma de pagament no vàlida.',
    'no_iban': 'Algun contracte no té compte bancari per domiciliar-lo.',
    'already_closed': 'El procés ja està tancat.',
    'close_before_start': "La data de tancament no pot ser anterior a l'inici de l'anomalia.",
    'invalid_target': 'Estat de destinació no vàlid.',
    'no_invoices': 'Cal seleccionar alguna factura.',
    'invalid_invoices': "Alguna factura no és del procés o ja no es pot passar a aquest estat.",
    'missing_status': "No hi ha configurat l'estat de morositat o d'irrecuperable.",
}
GENERIC_ERROR_MESSAGE = "No s'ha pogut desar el procés d'insolvència."


class InsolvencyProcessError(ValueError):
    """Dades del procés no vàlides: `code` és una clau d'ERROR_MESSAGES (es retorna un 400)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def insolvency_error_message(code):
    return ERROR_MESSAGES.get(code, GENERIC_ERROR_MESSAGE)


def _config_value(token, default=None):
    config = ConfigProject.objects.filter(token=token).first()
    return config.value if config else default


def current_insolvent_anomalies():
    return PersonAnomaly.objects.filter(PersonAnomaly.current_q(), anomaly_type__token=INSOLVENT_ANOMALY_TOKEN)


def insolvent_person_exists(person_ref):
    """Exists() per anotar o filtrar querysets: `person_ref` és l'OuterRef de l'id de la persona."""
    return Exists(current_insolvent_anomalies().filter(person_id=person_ref))


def is_person_insolvent(person):
    return bool(person) and current_insolvent_anomalies().filter(person=person).exists()


# ---------------------------------------------------------------------------
# Previsualització: factures i contractes de la persona
# ---------------------------------------------------------------------------

def excluded_invoice_status_tokens():
    """Estats de factura que no compten com a emeses: esborrany, anul·lada i donada de baixa."""
    return [value for value in (
        _config_value('invoice_status_pending_token'),
        _config_value('invoice_status_cancelled_token'),
        _config_value('invoice_status_dropped_token'),
    ) if value]


def eligible_invoices(person, start_date, excluded_status=None):
    """Factures emeses de la persona des de la data d'insolvència (sense anul·lades ni esborranys).
    `excluded_status`: els tokens ja calculats, per no tornar-los a llegir a cada fila d'un llistat."""
    from billing.models import Invoice
    if excluded_status is None:
        excluded_status = excluded_invoice_status_tokens()
    return (
        Invoice.objects.filter(person=person, issue_date__gte=start_date)
        .exclude(status__token__in=excluded_status)
        .select_related('status')
        .order_by('issue_date', 'id')
    )


def holder_contracts(person):
    """Contractes actius on la persona és titular."""
    from contract.models import Contract
    return (
        Contract.objects.filter(holder=person, is_active=True)
        .select_related('payment__type', 'status', 'debt_management')
        .order_by('token', 'id')
    )


# ---------------------------------------------------------------------------
# Persones amb un procés obert: fora de les reclamacions de deute i dels talls
# ---------------------------------------------------------------------------

def open_insolvency_person_ids():
    """Ids de les persones amb un procés d'insolvència obert (llista precalculada per filtrar)."""
    from billing.models import InsolvencyProcess
    return list(
        InsolvencyProcess.objects.filter(status=InsolvencyProcess.STATUS_OPEN).values_list('person_id', flat=True)
    )


def insolvent_supply_point_ids(supply_point_ids):
    """Dels punts de subministrament donats, els que tenen un contracte actiu amb el titular
    en un procés d'insolvència obert."""
    from django.db.models import Q
    from contract.models import Contract
    person_ids = open_insolvency_person_ids()
    if not supply_point_ids or not person_ids:
        return []
    point_ids = set(supply_point_ids)
    contracts = Contract.objects.filter(
        Q(supply_points__id__in=point_ids) | Q(supply_point_default_id__in=point_ids),
        is_active=True, holder_id__in=person_ids,
    ).values_list('supply_points__id', 'supply_point_default_id')
    found = set()
    for m2m_id, default_id in contracts:
        found.update(value for value in (m2m_id, default_id) if value in point_ids)
    return sorted(found)


# ---------------------------------------------------------------------------
# Canvis als contractes: forma de pagament i gestió d'impagats
# ---------------------------------------------------------------------------

def insolvent_debt_management():
    """Valor «Insolvent» de la gestió d'impagats del contracte (si el catàleg el té)."""
    from contract.models import ContractDebtManagement
    return ContractDebtManagement.objects.filter(token=INSOLVENT_DEBT_MANAGEMENT_TOKEN).first()


def _apply_payment_type(contract, new_type, user):
    """Nova forma de pagament per al contracte amb el tipus indicat (les dades bancàries i de
    facturació electrònica es mantenen). Es fa amb update() perquè desar el contracte no dispari
    els senyals de baixa (retorn de fiances); el canvi queda a ContractLog i ContractDataChange.
    Retorna (tipus antic, forma nova), o None si el tipus ja és el mateix."""
    from billing.models import GeneralPayment
    from contract.models import Contract, ContractDataChange, ContractLog

    old_payment = contract.payment
    old_type = old_payment.type if old_payment else None
    if old_type and old_type.id == new_type.id:
        return None
    direct_debit_token = _config_value('direct_debit_token', 'DIRECT_DEBIT')
    if new_type.token == direct_debit_token and not (old_payment and old_payment.IBAN_id):
        raise InsolvencyProcessError('no_iban')

    new_payment = GeneralPayment.objects.create(
        token=f"{contract.token}_{new_type.token}",
        type=new_type,
        IBAN=old_payment.IBAN if old_payment else None,
        company_iban=old_payment.company_iban if old_payment else None,
        dir3=old_payment.dir3 if old_payment else None,
        accounting_office=old_payment.accounting_office if old_payment else None,
        managing_body=old_payment.managing_body if old_payment else None,
        processing_unit=old_payment.processing_unit if old_payment else None,
        command=old_payment.command if old_payment else None,
        record=old_payment.record if old_payment else None,
        mandate_id=old_payment.mandate_id if old_payment else None,
    )
    Contract.objects.filter(pk=contract.pk).update(payment=new_payment, updated_at=timezone.now())
    ContractLog.objects.create(
        contract=contract,
        field_name='payment',
        old_value=str(old_payment) if old_payment else None,
        new_value=str(new_payment),
        operation_token=str(uuid.uuid4()),
        user=user,
    )
    ContractDataChange.objects.create(
        contract=contract,
        previous_payment_type=old_type,
        new_payment_type=new_type,
        previous_payment=old_payment.IBAN if old_payment else None,
        new_payment=new_payment.IBAN,
        new_general_payment=new_payment,
        user=user,
        approved_at=timezone.now(),
    )
    # La forma antiga es desactiva només si ja no la fa servir cap altre contracte
    if old_payment and not Contract.objects.filter(payment=old_payment).exists():
        old_payment.is_active = False
        old_payment.save(update_fields=['is_active', 'updated_at'])
    contract.payment = new_payment
    return old_type, new_payment


def change_contract_payment_type(contract_row, new_type, user):
    """Canvi de forma de pagament d'un contracte del procés; queda a la fila del contracte."""
    result = _apply_payment_type(contract_row.contract, new_type, user)
    if not result:
        return None
    old_type, new_payment = result
    contract_row.previous_payment_type = old_type
    contract_row.new_payment_type = new_type
    contract_row.general_payment = new_payment
    contract_row.save(update_fields=['previous_payment_type', 'new_payment_type', 'general_payment'])
    return contract_row


def _set_debt_management(contract, debt_management, user):
    """Gestió d'impagats del contracte amb update() (sense senyals de desar) i ContractLog."""
    from contract.models import Contract, ContractLog
    old_value = contract.debt_management
    Contract.objects.filter(pk=contract.pk).update(debt_management=debt_management, updated_at=timezone.now())
    ContractLog.objects.create(
        contract=contract,
        field_name='debt_management',
        old_value=str(old_value) if old_value else None,
        new_value=str(debt_management) if debt_management else None,
        operation_token=str(uuid.uuid4()),
        user=user,
    )
    contract.debt_management = debt_management


# ---------------------------------------------------------------------------
# Alta i tancament del procés
# ---------------------------------------------------------------------------

def _parse_ids(raw):
    if raw in (None, ''):
        return []
    if not isinstance(raw, list):
        raise InsolvencyProcessError('invalid_ids')
    ids = []
    for value in raw:
        if isinstance(value, bool) or not (isinstance(value, int) or (isinstance(value, str) and value.isdigit())):
            raise InsolvencyProcessError('invalid_ids')
        ids.append(int(value))
    return ids


def create_insolvency_process(*, person, kind, start_date, user, case_number=None, observation=None,
                              payment_changes=None):
    """Crea el procés: anomalia «Insolvent», totes les factures emeses des de la data, gestió
    d'impagats «Insolvent» als contractes on és titular i canvis de forma de pagament.

    `payment_changes`: llista de {"contract_id": id, "payment_type_id": id}.
    Tot es valida abans d'escriure res; si alguna cosa falla, no queda res a mitges.
    """
    from billing.models import InsolvencyProcess, InsolvencyProcessContract
    from contract.models import PaymentType

    if kind not in dict(InsolvencyProcess.KIND_CHOICES):
        raise InsolvencyProcessError('invalid_kind')
    if InsolvencyProcess.objects.filter(person=person, status=InsolvencyProcess.STATUS_OPEN).exists():
        raise InsolvencyProcessError('already_open')
    anomaly_type = PersonAnomalyType.objects.filter(token=INSOLVENT_ANOMALY_TOKEN).first()
    if not anomaly_type:
        raise InsolvencyProcessError('missing_anomaly_type')

    contracts = {contract.id: contract for contract in holder_contracts(person)}

    # Canvis de forma de pagament: només contractes on és titular i tipus que existeixen
    changes = {}
    if payment_changes not in (None, ''):
        if not isinstance(payment_changes, list):
            raise InsolvencyProcessError('invalid_payment_changes')
        for change in payment_changes:
            if not isinstance(change, dict):
                raise InsolvencyProcessError('invalid_payment_changes')
            contract_id, type_id = _parse_ids([change.get('contract_id'), change.get('payment_type_id')])
            if contract_id in changes:
                raise InsolvencyProcessError('invalid_payment_changes')
            if contract_id not in contracts:
                raise InsolvencyProcessError('invalid_contract')
            payment_type = PaymentType.objects.filter(id=type_id).first()
            if not payment_type:
                raise InsolvencyProcessError('invalid_payment_type')
            changes[contract_id] = payment_type

    debt_management = insolvent_debt_management()
    from coredata.utils.person_anomaly_log import describe_anomaly, log_anomaly_change
    with transaction.atomic():
        anomaly = current_insolvent_anomalies().filter(person=person).order_by('start_date').first()
        if not anomaly:
            anomaly = PersonAnomaly.objects.create(
                person=person,
                anomaly_type=anomaly_type,
                start_date=start_date,
                observation=observation,
                user=user,
            )
            log_anomaly_change(anomaly, user, None, describe_anomaly(anomaly))
        process = InsolvencyProcess.objects.create(
            person=person,
            kind=kind,
            start_date=start_date,
            case_number=case_number or None,
            observation=observation or None,
            anomaly=anomaly,
            user=user,
        )
        process.invoices.set(eligible_invoices(person, start_date))
        for contract in contracts.values():
            row = InsolvencyProcessContract.objects.create(
                process=process,
                contract=contract,
                previous_debt_management=contract.debt_management,
            )
            if debt_management and contract.debt_management_id != debt_management.id:
                _set_debt_management(contract, debt_management, user)
                row.debt_management_changed = True
                row.save(update_fields=['debt_management_changed'])
            if contract.id in changes:
                change_contract_payment_type(row, changes[contract.id], user)
    return process


def close_insolvency_process(process, user, end_date=None, restore_payment=False):
    """Tanca el procés: hi deixa totes les factures emeses des de la data, resol l'anomalia
    «Insolvent», torna la gestió d'impagats d'abans (si ningú no l'ha canviada) i, si es demana,
    la forma de pagament d'abans (si el contracte encara té la que es va posar al procés)."""
    from billing.models import InsolvencyProcess
    from contract.models import Contract
    from coredata.utils.person_anomaly_log import describe_anomaly, log_anomaly_change

    if process.status != InsolvencyProcess.STATUS_OPEN:
        raise InsolvencyProcessError('already_closed')
    end_date = end_date or timezone.now().date()
    anomaly = process.anomaly
    if anomaly and anomaly.is_current and end_date < anomaly.start_date:
        raise InsolvencyProcessError('close_before_start')
    debt_management = insolvent_debt_management()
    with transaction.atomic():
        process.status = InsolvencyProcess.STATUS_CLOSED
        process.closed_at = timezone.now()
        process.closed_by = user
        process.save(update_fields=['status', 'closed_at', 'closed_by', 'updated_at'])
        process.invoices.set(eligible_invoices(process.person, process.start_date))
        if anomaly and anomaly.is_current:
            old_value = describe_anomaly(anomaly)
            anomaly.end_date = end_date
            anomaly.save(update_fields=['end_date', 'updated_at'])
            log_anomaly_change(anomaly, user, old_value, describe_anomaly(anomaly))
        for row in process.contracts.select_related('previous_payment_type', 'previous_debt_management'):
            contract = Contract.objects.select_related('payment__type', 'debt_management').get(pk=row.contract_id)
            update_fields = []
            if (row.debt_management_changed and debt_management
                    and contract.debt_management_id == debt_management.id):
                _set_debt_management(contract, row.previous_debt_management, user)
                row.debt_management_restored = True
                update_fields.append('debt_management_restored')
            if (restore_payment and row.new_payment_type_id and row.previous_payment_type_id
                    and row.general_payment_id and contract.payment_id == row.general_payment_id):
                _apply_payment_type(contract, row.previous_payment_type, user)
                row.payment_restored = True
                update_fields.append('payment_restored')
            if update_fields:
                row.save(update_fields=update_fields)
    return process


# ---------------------------------------------------------------------------
# Factures del procés a morositat o irrecuperable (decisió manual de l'usuari)
# ---------------------------------------------------------------------------

TARGET_ENDOWMENT = 'endowment'
TARGET_IRRECOVERABLE = 'irrecoverable'


def process_invoices(process, excluded_status=None):
    """Factures del procés: obert, totes les emeses des de la data; tancat, les que hi havia en tancar-lo."""
    from billing.models import InsolvencyProcess
    if process.status == InsolvencyProcess.STATUS_OPEN:
        return eligible_invoices(process.person, process.start_date, excluded_status)
    return process.invoices.select_related('status').order_by('issue_date', 'id')


def delinquency_status_tokens():
    """Tokens d'estat de factura: els pendents de cobrar, morositat i irrecuperable."""
    return {
        'pending': [value for value in (
            _config_value('invoice_status_confirmed_token'),
            _config_value('invoice_status_expired_token'),
        ) if value],
        TARGET_ENDOWMENT: _config_value('invoice_status_endowment_token'),
        TARGET_IRRECOVERABLE: _config_value('invoice_status_irrecoverable_token'),
    }


def delinquency_targets(invoice, tokens):
    """Estats als quals es pot passar la factura, com a la gestió de morositat: una pendent de
    cobrar pot anar a morositat o a irrecuperable; una en morositat, només a irrecuperable."""
    if not invoice.total_final or invoice.total_final <= 0:
        return []
    status_token = invoice.status.token if invoice.status_id and invoice.status else None
    if not status_token:
        return []
    if status_token == tokens[TARGET_ENDOWMENT]:
        return [TARGET_IRRECOVERABLE]
    if status_token in tokens['pending']:
        return [TARGET_IRRECOVERABLE] if invoice.endowment_date else [TARGET_ENDOWMENT, TARGET_IRRECOVERABLE]
    return []


def change_invoices_delinquency_status(process, invoice_ids, target, user):
    """Passa les factures seleccionades del procés a morositat o a irrecuperable.

    Igual que la gestió de morositat: estat de la factura, data de morositat i/o d'irrecuperable,
    i els cobraments pendents al mateix estat. Queda a l'historial d'estats de cada factura i de
    cada cobrament. Si alguna factura no és del procés o no es pot passar a l'estat, no es canvia res.
    """
    from billing.models import Invoice, InvoiceStatus, Payment, PaymentStatus
    from billing.utils.payment_service import log_invoice_status, log_payment_status

    if target not in (TARGET_ENDOWMENT, TARGET_IRRECOVERABLE):
        raise InsolvencyProcessError('invalid_target')
    ids = set(_parse_ids(invoice_ids))
    if not ids:
        raise InsolvencyProcessError('no_invoices')
    tokens = delinquency_status_tokens()
    invoice_status = InvoiceStatus.objects.filter(token=tokens[target]).first() if tokens[target] else None
    payment_token = _config_value(f'payment_status_{target}_token')
    payment_status = PaymentStatus.objects.filter(token=payment_token).first() if payment_token else None
    if not invoice_status or not payment_status:
        raise InsolvencyProcessError('missing_status')
    # Cobraments que ja no estan pendents: no es toquen
    settled_payment_tokens = [value for value in (
        _config_value('payment_status_paid_token'),
        _config_value('payment_status_piggy_token'),
        _config_value('payment_status_cancelled_token'),
        _config_value('payment_status_payoff_token'),
        _config_value('payment_status_dropped_token'),
    ) if value]

    today = timezone.now().date()
    with transaction.atomic():
        if set(process_invoices(process).filter(id__in=ids).values_list('id', flat=True)) != ids:
            raise InsolvencyProcessError('invalid_invoices')
        # Es bloquegen i es tornen a validar: l'estat pot haver canviat des que es va carregar la llista
        invoices = list(Invoice.objects.select_for_update().filter(id__in=ids).order_by('id'))
        for invoice in invoices:
            if target not in delinquency_targets(invoice, tokens):
                raise InsolvencyProcessError('invalid_invoices')
        for invoice in invoices:
            log_invoice_status(invoice, invoice_status, user)
            fields = {'status': invoice_status}
            if target == TARGET_ENDOWMENT or not invoice.endowment_date:
                fields['endowment_date'] = today
            if target == TARGET_IRRECOVERABLE:
                fields['irrecoverable_date'] = today
            # update(): sense els senyals de desar la factura, com la gestió de morositat
            Invoice.objects.filter(pk=invoice.pk).update(**fields)
        payments = list(
            Payment.objects.filter(invoice_id__in=ids)
            .exclude(status__token__in=settled_payment_tokens)
            .exclude(status=payment_status)
            .select_related('status')
        )
        for payment in payments:
            log_payment_status(payment, payment_status, user, today)
        Payment.objects.filter(id__in=[payment.id for payment in payments]).update(status=payment_status)
    return len(invoices)


# ---------------------------------------------------------------------------
# Avisos a la facturació i a les remeses
# ---------------------------------------------------------------------------

def insolvent_holder_contracts(contracts):
    """Dels contractes donats, els que tenen el titular insolvent."""
    return contracts.filter(insolvent_person_exists(OuterRef('holder_id'))).select_related('holder')
