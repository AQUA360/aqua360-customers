"""Procés d'insolvència d'una persona (#2633).

- En crear-lo s'activa l'anomalia «Insolvent» de la persona (o es reutilitza la vigent).
- Les factures emeses des de la data d'insolvència segueixen la facturació normal; l'usuari pot
  vincular-les al procés en crear-lo.
- Des del procés es pot canviar la forma de pagament dels contractes on la persona és titular.
- Mentre la persona és insolvent, la facturació i la generació de remeses n'avisen.
"""
import uuid

from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from coredata.models import ConfigProject, PersonAnomaly, PersonAnomalyType


INSOLVENT_ANOMALY_TOKEN = 'insolvent'


# Missatges per a l'usuari, per codi: la resposta de l'API mai no porta el text de l'excepció
ERROR_MESSAGES = {
    'invalid_person': 'Persona no vàlida.',
    'invalid_date': 'Data no vàlida.',
    'invalid_kind': 'invalid_kind',
    'already_open': "La persona ja té un procés d'insolvència obert.",
    'missing_anomaly_type': "No hi ha el tipus d'anomalia «Insolvent».",
    'invalid_ids': 'Identificadors no vàlids.',
    'invalid_invoices': "Alguna factura no és de la persona o és anterior a la data d'insolvència.",
    'invalid_payment_changes': 'Canvis de forma de pagament no vàlids.',
    'invalid_contract': 'invalid_contract',
    'invalid_payment_type': 'invalid_payment_type',
    'no_iban': 'Algun contracte no té compte bancari per domiciliar-lo.',
    'already_closed': 'already_closed',
    'close_before_start': "La data de tancament no pot ser anterior a l'inici de l'anomalia.",
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

def eligible_invoices(person, start_date):
    """Factures emeses de la persona des de la data d'insolvència (sense anul·lades ni esborranys)."""
    from billing.models import Invoice
    excluded_status = [value for value in (
        _config_value('invoice_status_pending_token'),
        _config_value('invoice_status_cancelled_token'),
        _config_value('invoice_status_dropped_token'),
    ) if value]
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
        .select_related('payment__type', 'status')
        .order_by('token', 'id')
    )


# ---------------------------------------------------------------------------
# Canvi de forma de pagament d'un contracte
# ---------------------------------------------------------------------------

def change_contract_payment_type(contract, new_type, user, process):
    """Nova forma de pagament per al contracte amb el tipus indicat (les dades bancàries i de
    facturació electrònica es mantenen). Es fa amb update() perquè desar el contracte no dispari
    els senyals de baixa (retorn de fiances); el canvi queda a ContractLog i ContractDataChange."""
    from billing.models import GeneralPayment, InsolvencyProcessContract
    from contract.models import Contract, ContractDataChange, ContractLog

    old_payment = contract.payment
    old_type = old_payment.type if old_payment else None
    if old_type and old_type.id == new_type.id:
        return None
    direct_debit_token = _config_value('direct_debit_token', 'DIRECT_DEBIT')
    if new_type.token == direct_debit_token and not (old_payment and old_payment.IBAN_id):
        raise InsolvencyProcessError(
            'no_iban'
        )

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
    return InsolvencyProcessContract.objects.create(
        process=process,
        contract=contract,
        previous_payment_type=old_type,
        new_payment_type=new_type,
        general_payment=new_payment,
    )


# ---------------------------------------------------------------------------
# Alta i tancament del procés
# ---------------------------------------------------------------------------

def _parse_ids(raw, field):
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
                              invoice_ids=None, payment_changes=None):
    """Crea el procés: anomalia «Insolvent», factures vinculades i canvis de forma de pagament.

    `payment_changes`: llista de {"contract_id": id, "payment_type_id": id}.
    Tot es valida abans d'escriure res; si alguna cosa falla, no queda res a mitges.
    """
    from billing.models import InsolvencyProcess
    from contract.models import PaymentType

    if kind not in dict(InsolvencyProcess.KIND_CHOICES):
        raise InsolvencyProcessError('invalid_kind')
    if InsolvencyProcess.objects.filter(person=person, status=InsolvencyProcess.STATUS_OPEN).exists():
        raise InsolvencyProcessError('already_open')
    anomaly_type = PersonAnomalyType.objects.filter(token=INSOLVENT_ANOMALY_TOKEN).first()
    if not anomaly_type:
        raise InsolvencyProcessError('missing_anomaly_type')

    # Factures: només les emeses de la persona des de la data
    invoice_ids = _parse_ids(invoice_ids, 'invoice_ids')
    invoices = list(eligible_invoices(person, start_date).filter(id__in=invoice_ids))
    if len(invoices) != len(set(invoice_ids)):
        raise InsolvencyProcessError('invalid_invoices')

    # Canvis de forma de pagament: només contractes on és titular i tipus que existeixen
    changes = []
    if payment_changes not in (None, ''):
        if not isinstance(payment_changes, list):
            raise InsolvencyProcessError('invalid_payment_changes')
        contracts = {contract.id: contract for contract in holder_contracts(person)}
        seen = set()
        for change in payment_changes:
            if not isinstance(change, dict):
                raise InsolvencyProcessError('invalid_payment_changes')
            contract_id, type_id = _parse_ids([change.get('contract_id'), change.get('payment_type_id')], 'payment_changes')
            if contract_id in seen:
                raise InsolvencyProcessError('invalid_payment_changes')
            seen.add(contract_id)
            contract = contracts.get(contract_id)
            if not contract:
                raise InsolvencyProcessError('invalid_contract')
            payment_type = PaymentType.objects.filter(id=type_id).first()
            if not payment_type:
                raise InsolvencyProcessError('invalid_payment_type')
            changes.append((contract, payment_type))

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
        if invoices:
            process.invoices.set(invoices)
        for contract, payment_type in changes:
            change_contract_payment_type(contract, payment_type, user, process)
    return process


def close_insolvency_process(process, user, end_date=None):
    """Tanca el procés i resol l'anomalia «Insolvent» que va activar."""
    from billing.models import InsolvencyProcess
    from coredata.utils.person_anomaly_log import describe_anomaly, log_anomaly_change

    if process.status != InsolvencyProcess.STATUS_OPEN:
        raise InsolvencyProcessError('already_closed')
    end_date = end_date or timezone.now().date()
    with transaction.atomic():
        process.status = InsolvencyProcess.STATUS_CLOSED
        process.closed_at = timezone.now()
        process.closed_by = user
        process.save(update_fields=['status', 'closed_at', 'closed_by', 'updated_at'])
        anomaly = process.anomaly
        if anomaly and anomaly.is_current:
            if end_date < anomaly.start_date:
                raise InsolvencyProcessError('close_before_start')
            old_value = describe_anomaly(anomaly)
            anomaly.end_date = end_date
            anomaly.save(update_fields=['end_date', 'updated_at'])
            log_anomaly_change(anomaly, user, old_value, describe_anomaly(anomaly))
    return process


# ---------------------------------------------------------------------------
# Avisos a la facturació i a les remeses
# ---------------------------------------------------------------------------

def insolvent_holder_contracts(contracts):
    """Dels contractes donats, els que tenen el titular insolvent."""
    return contracts.filter(insolvent_person_exists(OuterRef('holder_id'))).select_related('holder')
