import datetime
import os
import re
import uuid
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import make_aware
from billing.models import EstimatedBag, GeneralPayment, GeneralPaymentMandateLog, Reading, Invoice
from billing.utils.request_initial_reading_service import move_newer_readings_to_contract
from order.models import Order
from documentmanager.models import DocumentSign
from claimrequest.models import VulnerabilityRequest
from coredata.utils.name_utils import generate_token
from coredata.utils.iban_validator_utils import get_spanish_bank_code_candidates
from logger.models import LogContractChange, LogContractTotalMembers, LogContractPhones
from notification.models import Notification
from pricing.models import LineItemType
from contract.models import BailStatus, Contract, ContractDataChange, ContractRepresentative, ContractRequestStatus, ContractRequestType, ContractStatus, ContractRequest, Bail, BailType, ContractRequestRepresentative, ContractTerminationRequest, ContractTerminationStatus, PaymentType, PiggyBank, PiggyBankMovement, Variable, ContractClause, ContractRequestDocumentation, Bonification
from coredata.models import Bank, ConfigProject, Country, Person, PersonBank, PersonContact
from django.utils import timezone
from datetime import datetime

from service.models import Meter, MeterStatus, SupplyPointStatus

def _create_fictitious_meter(no_meter_status):
    from coredata.utils.name_utils import generate_token
    base_token = f"SC{generate_token(Meter)}"
    return Meter.objects.create(
        token=base_token,
        code=base_token,
        status=no_meter_status,
        installation_at=timezone.now().date(),
        is_active=True,
    )


def _rename_old_contract_and_get_reused_token(contract_request):
    """Per a un canvi de nom amb keep_same_code=True, renombra el(s) contracte(s)
    donat(s) de baixa afegint-los un sufix incremental (/000N) i retorna el codi
    (token) original perquè el reutilitzi el nou contracte."""
    termination_requests = list(contract_request.contract_termination_requests.all())
    if len(termination_requests) != 1:
        raise Exception(
            "keep_same_code només es pot fer servir quan la sol·licitud de canvi de nom "
            "té exactament una ContractTerminationRequest vinculada."
        )
    termination_request = termination_requests[0]
    old_contract = termination_request.contract
    if not old_contract:
        raise Exception("keep_same_code: la ContractTerminationRequest vinculada no té contracte.")

    base_token = re.sub(r'/\d+$', '', old_contract.token) if old_contract.token else old_contract.token

    completed_terminations = ContractTerminationRequest.objects.filter(
        contract__token__regex=fr'^{re.escape(base_token)}(/\d+)?$',
        approved_at__isnull=False,
    ).exclude(id=termination_request.id).count()
    next_suffix = completed_terminations + 1

    old_contract.token = f"{base_token}/{next_suffix:04d}"
    old_contract.save()

    # No facturar la lectura de tall d'immediat: es deixa vinculada al nou contracte
    # (alta) i es factura amb la resta de lectures pendents al proper cicle de
    # facturació (trimestral).
    if termination_request.bill_cut_reading:
        termination_request.bill_cut_reading = False
        termination_request.save()

    return base_token, termination_request


# Create Contract from ContractRequest
def contract_create(user, contract_request_id):
    # select_for_update bloqueja la fila del ContractRequest fins al commit: si dues
    # peticions arriben gairebé alhora (doble clic), la segona espera i, en veure que
    # ja hi ha un Contract creat, el retorna en lloc de duplicar-lo.
    with transaction.atomic():
        contract_request = ContractRequest.objects.select_for_update().get(id=contract_request_id)
        existing_contract = contract_request.contract.first()
        if existing_contract:
            return existing_contract
        return _contract_create_locked(user, contract_request)


def _contract_create_locked(user, contract_request):
    contract_status = ContractStatus.objects.get(is_default=True)

    contract_request_type_default = ContractRequestType.objects.filter(has_persons=True).first() # TODO: això s'hauria de substuir per un de configurat.

    reused_termination_request = None
    contract_token = contract_request.token
    if contract_request.is_change_of_name and contract_request.keep_same_code:
        contract_token, reused_termination_request = _rename_old_contract_and_get_reused_token(contract_request)

        # El mandat SEPA es va generar quan es va donar d'alta la sol·licitud,
        # amb el token propi de la ContractRequest (no el codi reutilitzat del
        # contracte de baixa). Un cop resolt el codi final, cal regenerar-lo
        # perquè el mandat coincideixi amb el número de contracte definitiu.
        payment = contract_request.payment
        if payment is not None:
            from billing.utils.payment_service import generate_mandate_id

            previous_mandate_id = payment.mandate_id
            new_mandate_id = generate_mandate_id(payment, contract_token)
            if new_mandate_id != previous_mandate_id:
                GeneralPaymentMandateLog.objects.create(
                    general_payment=payment,
                    previous_mandate_id=previous_mandate_id,
                    new_mandate_id=new_mandate_id,
                    user=user,
                    is_manual=False,
                )
                payment.mandate_id = new_mandate_id
                payment.save()

    piggy_bank = PiggyBank.objects.create(
        token=f"{contract_token}",
        person=contract_request.holder,
        amount=0.00
    )

    data = {
        'token': contract_token,
        'company': contract_request.company if contract_request.company else None,
        'mandate_id': contract_request.payment.mandate_id if contract_request.payment and contract_request.payment.mandate_id else None,
        'supply_point_default': contract_request.supply_point_default,
        'owner': contract_request.owner if contract_request.owner else None,
        'tenant': contract_request.tenant if contract_request.tenant else None,
        'holder': contract_request.holder,
        'address_billing': contract_request.address_billing if contract_request.address_billing else None,
        'address_contact': contract_request.address_contact if contract_request.address_contact else None,
        'payment': contract_request.payment if contract_request.payment else None,
        'contract_request': contract_request,
        'status': contract_status,
        'use_type': contract_request.use_type if contract_request.use_type else None,
        'client_type': contract_request.client_type if contract_request.client_type else None,
        'category': contract_request.category if contract_request.category else None,
        "communication_type": contract_request.communication_type if contract_request.communication_type else None,
        "person_contact_email": contract_request.person_contact_email if contract_request.person_contact_email else None,
        "total_persons": contract_request.total_persons if contract_request.total_persons else None,
        "contract_request_type": contract_request.type if contract_request.type else contract_request_type_default,
        "contract_file": contract_request.contract_file if contract_request.contract_file else None,
        "remittance_date": contract_request.remittance_date if contract_request.remittance_date else None,
        "debt_management": contract_request.debt_management if contract_request.debt_management else None,
        "registration_date": contract_request.registration_date,
        "piggy_bank": piggy_bank,
        "bill_full_period": contract_request.bill_full_period,
        "language": contract_request.language if contract_request.language else settings.LANGUAGE,
    }

    
    contract = Contract.objects.create(**data)
    
    """ try:
        notification_save = {
            'token': uuid.uuid4(),
            'name': f"Contracte creat",
            'description': f"Contracte creat de la sol·licitud de contracte {contract_request.token}",
            'module': 'contract',
            'entity': 'contracts',
            'object_id': contract.id,
            'is_active': True
        }
        
        Notification.objects.create(**notification_save)
    except:
        print("Could not create notification for contract creation") """
    
    try:
        vulnerability_request = VulnerabilityRequest.objects.get(contract_request__token=contract_request.token)
        vulnerability_request.contract = contract
        contract_person = contract.tenant if contract.tenant and contract.holder.is_juridic else contract.holder
        contract_person.vulnerability_level = 2
        contract_person.save()
        vulnerability_request.person = contract_person
        vulnerability_request.save()
    except:
        pass
    
    if contract_request.contacts:
        contract.contacts.set(contract_request.contacts.all())
    
    if contract_request.person_contact_sms:
        contract.person_contact_sms.set(contract_request.person_contact_sms.all())
    
    # print(f"contract created: {contract.id}")
    
    # Duplicate supply points from contract_request to contract
    
    contract.supply_points.set([contract_request.supply_point_default])
    supply_point_active_status_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
    supply_point_active_status = SupplyPointStatus.objects.get(token=supply_point_active_status_token)

    meter_active_status_token = ConfigProject.objects.get(token='meter_status_active_token').value
    meter_active_status = MeterStatus.objects.get(token=meter_active_status_token)

    meter_ids = []

    if contract_request.supply_points.exists():
        contract.supply_points.add(*contract_request.supply_points.all())
        contract.supply_points.update(status=supply_point_active_status)

        for supply_point in contract.supply_points.all():
            if supply_point.meter:
                supply_point.meter.status = meter_active_status
                supply_point.meter.installation_at = timezone.now().date()
                supply_point.meter.uninstallation_at = None
                supply_point.meter.save()
                meter_ids.append(supply_point.meter.id)
            else:
                meter_no_meter_status_token = ConfigProject.objects.get(token='token_meter_status_no_meter').value
                meter_no_meter_status = MeterStatus.objects.get(token=meter_no_meter_status_token)
                fictitious_meter = _create_fictitious_meter(meter_no_meter_status)
                supply_point.meter = fictitious_meter
                supply_point.save()
    
    """ if contract_request.contract_file:
        original_filename = os.path.basename(contract_request.contract_file.name)
        contract.contract_file.save(original_filename, contract_request.contract_file)
        contract.save()
     """
    # Per cada BailType de la ContractRequest, crear un Bail
    """ for bail_type in contract_request.bail_types.all():
        bail = Bail.objects.create(type=bail_type)
        contract.bails.add(bail) """
    
    # AFEGIR LECTURES INICIALS
    readings = Reading.objects.filter(
        contract_request=contract_request,
        is_initial=True,
        # meter__id__in=meter_ids,
    )
    for reading in readings:
        # "Facturar període complert": lectura existent del contracte anterior traspassada com
        # a inicial (request-transfer-reading/). Només canvia de contracte: no es toquen els
        # valors, la data, el consum ni els dies del període. Les lectures inicials noves no
        # tenen contracte fins aquí; en un canvi de nom mantenint el codi el contracte pot ser
        # el mateix, per això no es compara amb `contract`.
        if reading.contract_id:
            reading.contract = contract
            reading.is_active = True
            reading.save(update_fields=['contract', 'is_active', 'updated_at'])
            continue
        reading.contract = contract
        reading.is_active = True
        if not reading.reading_date:
            reading.reading_date = contract.registration_date if contract.registration_date else contract.created_at.date()
        reading.calculated_value = 0
        reading.real_consumption = 0
        if not reading.supply_point:
            reading.supply_point = reading.meter.supply_points.filter(contracts__id=contract.id).first()
        reading.save()

    # Si s'ha triat com a inicial una lectura antiga del comptador, les lectures posteriors
    # (pendents de facturar) dels contractes donats de baixa passen al contracte nou.
    for reading in readings:
        move_newer_readings_to_contract(contract_request, contract, reading)

    # Si aquesta ContractRequest és l'alta que factura la lectura de tall d'una baixa
    # (bill_cut_reading=True), la factura ja es va generar en el seu moment vinculada a la
    # ContractRequest (Invoice.contract_request) perquè el Contract encara no existia
    # (invoice_service.invoice_contract_termination_generate). Ara que el contracte ja
    # existeix, vinculem aquestes factures al Contract definitiu.
    
    Invoice.objects.filter(contract_request=contract_request, contract__isnull=True).update(contract=contract)

    # Canvi de nom mantenint el mateix codi: la lectura de tall del contracte donat
    # de baixa es vincula al nou contracte (alta) en lloc de facturar-se de seguida,
    # perquè es reculli junt amb la resta de lectures pendents al proper cicle de
    # facturació (trimestral).
    if reused_termination_request:
        termination_readings = reused_termination_request.readings.filter(is_active=True)
        for termination_reading in termination_readings:
            # La mateixa lectura de tall es pot haver introduït també com a
            # "lectura inicial" de l'alta (request-reading/), pel mateix comptador.
            # Unifiquem-les en una de sola per no duplicar-la a la factura.
            duplicate_initial_reading = Reading.objects.filter(
                contract=contract,
                meter=termination_reading.meter,
                is_initial=True,
            ).exclude(id=termination_reading.id).first()
            if duplicate_initial_reading:
                if not termination_reading.leak_value and duplicate_initial_reading.leak_value:
                    termination_reading.leak_value = duplicate_initial_reading.leak_value
                if not termination_reading.reading_date and duplicate_initial_reading.reading_date:
                    termination_reading.reading_date = duplicate_initial_reading.reading_date
                termination_reading.save()
                duplicate_initial_reading.delete()
        termination_readings.update(contract=contract, batch=None)

    # Les Order (ordres de treball) creades mentre encara era una ContractRequest només
    # quedaven vinculades a aquesta. Ara que el Contract definitiu ja existeix, les hi vinculem.
    Order.objects.filter(contract_request=contract_request, contract__isnull=True).update(contract=contract)
    # Els DocumentSign enviats a firmar durant la sol·licitud (abans que existís el Contract
    # definitiu) es vinculaven només a la ContractRequest. Ara que el contracte ja existeix,
    # els vinculem també al Contract definitiu, mantenint la referència a la sol·licitud original.
    DocumentSign.objects.filter(contract_request=contract_request, contract__isnull=True).update(contract=contract)

    # Duplicate representatives from contract_request to contract
    for representative in contract_request.representatives.all():
        ContractRepresentative.objects.create(
            contract=contract,
            token=representative.token,
            person=representative.person,
            type=representative.type
        )
    
    # Associate clauses with the new contract
    for clause in contract_request.clauses.all():
        clause.contract = contract
        clause.save()
        
    # Associate documentation files with the new contract
    for doc in contract_request.documentation_files.all():
        doc.contract = contract
        doc.save()
    
    # Associate bonifications with the new contract
    for bonification in contract_request.bonifications.all():
        bonification.contract = contract
        bonification.save()

        
    # Duplicate variables from contract_request to contract
    for variable in contract_request.variables.all():
        variable.contract = contract
        variable.save()

    if(contract_request.status.token != "3"):
        contract_request.status = ContractRequestStatus.objects.get(token="3")
        contract_request.save()
    
    if contract_request.cnaes.exists():
        contract.cnaes.set(contract_request.cnaes.all())
    
    if contract_request.price_rates.exists():
        contract.price_rates.set(contract_request.price_rates.all())
    
    if contract_request.registration_price_rates.exists():
        contract.registration_price_rates.set(contract_request.registration_price_rates.all())
    # logger
    
    reading_estimated = ConfigProject.objects.get(token='reading_estimated').value
    if reading_estimated.lower() == 'true':
        for supply_point in contract.supply_points.all():
            EstimatedBag.objects.create(
                token=contract.token,
                supply_point=supply_point,
                contract=contract,
                total_consumption=0,
            )
            
    LogContractChange.objects.create(
        contract=contract,
        user=user,
        action='create',
        field_changed='token',
        previous_value=None,
        current_value=contract.token,
        previous_related_id=None,
        current_related_id=contract.id,
        observation=None
    )
    
    try:
        from contract.management.commands.fill_contract_use_aca import fill_contract_use_aca
        fill_contract_use_aca(single_contract_id=contract.id)
    except Exception as e:
        print("Error [contract.utils.contract_service.contract_create]:  Error filling use_aca: ", e)
    
    create_bails(contract, piggy_bank)
    
    check_contract_terminations(contract)

    return contract

def get_connection_diameter(contract):
    if not contract:
        raise Exception("Error [contract.utils.contract_service.get_connection_diameter]:  Contract not found")
    if not contract.supply_point_default:
        raise Exception("Error [contract.utils.contract_service.get_connection_diameter]:  Supply point default not found")
    connection = contract.supply_point_default.connection
    if not connection:
        raise Exception("Error [contract.utils.contract_service.get_connection_diameter]:  Connection not found")
    if not connection.diameter:
        raise Exception("Error [contract.utils.contract_service.get_connection_diameter]:  Connection Diameter not found")
    return connection.diameter.name

def get_meter_caliber(contract):
    if not contract:
        return 15
    if not contract.supply_point_default:
        print("Error [contract.utils.contract_service.get_meter_caliber]:  Supply point default not found")
        return 15
    meter = contract.supply_point_default.meter
    if not meter:
        #raise Exception("Error [contract.utils.contract_service.get_meter_caliber]:  Meter not found")
        print("Error [contract.utils.contract_service.get_meter_caliber]:  Meter not found")
        return 15
    if not meter.caliber:
        #raise Exception("Error [contract.utils.contract_service.get_meter_caliber]:  Meter Caliber not found")
        print("Error [contract.utils.contract_service.get_meter_caliber]:  Meter Caliber not found")
        return 15
    return meter.caliber.name

def get_contract_bop_price_rate(contract):
    """Retorna el ContractPriceRate que fa de referència per a la tarifa BOP.

    Prioritza el registre marcat explícitament amb is_bop_reference; si cap
    n'està marcat, cau al primer price_rate actiu com a comportament de
    compatibilitat amb dades existents.
    """
    if not contract:
        return None
    qs = contract.price_rates.select_related(
        "price_rate__billing_range_active__publication"
    )
    reference = qs.filter(is_bop_reference=True, is_active=True).first()
    if reference:
        return reference
    return qs.filter(is_active=True).order_by("id").first()

def get_contract_tarifa_bop(contract):
    """Valor de la tarifa BOP del contracte, a partir de la publicació del rang de
    facturació actiu de la tarifa marcada com a referència.

    Prioritza `Publication.boe_number` (el número de BOE, el valor identificatiu que
    es vol mostrar) i cau a `Publication.boe_date` quan no està informat, que és el
    que es mostrava abans. La reserva és necessària perquè bona part de les
    publicacions existents encara no tenen el número informat i, sense ella, el camp
    quedaria buit a tots els contractes.
    """
    from contract.utils.contract_pdf_service import format_date_to_string

    contract_price_rate = get_contract_bop_price_rate(contract)
    if (
        contract_price_rate
        and contract_price_rate.price_rate
        and contract_price_rate.price_rate.billing_range_active
    ):
        pub = contract_price_rate.price_rate.billing_range_active.publication
        if pub:
            # `boe_number` és un CharField: pot arribar com a None o com a cadena buida.
            boe_number = (pub.boe_number or '').strip()
            if boe_number:
                return boe_number
            if pub.boe_date:
                return format_date_to_string(pub.boe_date)
    return None

# Variables que no es traspassen en un canvi de nom: les bonificacions ACA i les
# socials depenen del titular i s'han de tornar a sol·licitar.
CHANGE_OF_NAME_EXCLUDED_VARIABLE_TOKENS = ('aca', 'social')


def get_change_of_name_copyable_variables(old_contract):
    """Variables vigents del contracte anterior que es traspassen en un canvi de nom.
    Sense start_at/end_at es considera vigent (moltes variables importades no tenen dates)."""
    excluded = Q()
    for word in CHANGE_OF_NAME_EXCLUDED_VARIABLE_TOKENS:
        excluded |= Q(token__icontains=word) | Q(type__token__icontains=word)

    today = timezone.now().date()
    return old_contract.variables.filter(
        Q(start_at__isnull=True) | Q(start_at__lte=today),
        Q(end_at__isnull=True) | Q(end_at__gte=today),
        is_active=True,
    ).exclude(excluded).select_related('type')


def copy_change_of_name_variables(contract_request):
    """En un canvi de nom, copia a la sol·licitud les variables actives del contracte
    actiu del punt de subministrament, excepte les ACA/socials i les dels tipus que
    ja té la sol·licitud. Es copien (no es mouen) perquè el contracte antic conservi
    el seu historial; en crear el contracte es traspassen com la resta de variables
    de la sol·licitud."""
    supply_point = contract_request.supply_point_default
    if not supply_point:
        return
    active_contract_token = ConfigProject.objects.get(token='contract_active_token').value
    old_contract = supply_point.contracts.filter(status__token=active_contract_token).first()
    if not old_contract:
        return

    existing_type_ids = set(contract_request.variables.exclude(type__isnull=True).values_list('type_id', flat=True))
    variables = get_change_of_name_copyable_variables(old_contract)
    for variable in variables:
        if variable.type_id and variable.type_id in existing_type_ids:
            continue
        Variable.objects.create(
            token=f"VR-{generate_token(Variable)}",
            name=variable.name,
            type=variable.type,
            value=variable.value,
            start_at=variable.start_at,
            end_at=variable.end_at,
            contract_request=contract_request,
        )
        if variable.type_id:
            existing_type_ids.add(variable.type_id)


def get_variables_actives(contract):
    now = timezone.now()
    return contract.variables.filter(
        start_at__lte=now,
        end_at__gte=now
    ) | contract.variables.filter(
        start_at__lte=now,
        end_at__isnull=True
    )

def create_bails(contract, piggy_bank):
    for registration_price_rate in contract.registration_price_rates.filter(is_bail=True):
        line_item_types = LineItemType.objects.filter(billing_range=registration_price_rate.billing_range_active)
        for line_item in line_item_types:
            price = line_item.price
            proportional_price = line_item.proportional_price

            amount = price or proportional_price
            now_date_string = (datetime.now().date()).strftime("%d%m%Y")
            bail_status_unreturned_token = ConfigProject.objects.get(token='bail_status_unreturned_token').value
        
            data = {
                "token": generate_token(Bail),
                "contract": contract,
                "product": registration_price_rate.product,
                "price_rate": registration_price_rate,
                "amount": amount,
                "payment_date": None,
                "invoice": None,
                "return_date": None,
                "status": BailStatus.objects.get(token=bail_status_unreturned_token),
                "created_at": timezone.now(),
                "updated_at":timezone.now(),
                "is_active":True,
                "is_billing":True
            }
            
            bail = Bail.objects.create(**data)
            contract.bails.add(bail)
            
            """ piggy_bank_movement = PiggyBankMovement.objects.create(
                token=generate_token(PiggyBankMovement),
                piggy_bank=piggy_bank,
                bail=bail,
                amount=amount,
                movement_date=timezone.now(),
                is_positive=True,
            )
            piggy_bank.amount += amount
            piggy_bank.save() """
    

def check_contract_terminations(contract):
    supply_points = contract.supply_points.all()
    termination_pending_status = ConfigProject.objects.get(token='contract_termination_pending_status').value
    termination_draft_status = ConfigProject.objects.get(token='contract_termination_draft').value
    contract_terminated_status_token = ConfigProject.objects.get(token='contract_terminated_status').value
    for supply_point in supply_points:
        supply_point_contracts = supply_point.contracts.all()
        for contract in supply_point_contracts:
            terminations = ContractTerminationRequest.objects.filter(contract=contract, status__token__in=[termination_pending_status, termination_draft_status])
            draft_termination = terminations.filter(status__token=termination_draft_status).first()
            if draft_termination:
                draft_termination.status = ContractTerminationStatus.objects.get(token=termination_pending_status)
                draft_termination.save()
            if terminations.count() > 0:
                contract.status = ContractStatus.objects.get(token=contract_terminated_status_token)
                contract.save()

def updateTotalMembers(user, data, new_contract):
    if new_contract.total_persons != data.get('total_persons') and data.get('total_persons'):
        LogContractTotalMembers.objects.create(
            object = new_contract,
            previous_total_persons = new_contract.total_persons,
            current_total_persons = data.get('total_persons'),
            user = user,
            timestamp = datetime.now(),
            observation = None
        )


def _format_phones_display(contacts):
    numbers = [contact.phone for contact in contacts if contact and contact.phone]
    return ', '.join(numbers) if numbers else '-'


def log_contract_phones_change(user, contract, phone_ids):
    """Registra canvis en la llista de telèfons del contracte (M2M contacts)."""
    if phone_ids is None:
        return

    previous_contacts = list(contract.contacts.all())
    previous_ids = sorted(contact.id for contact in previous_contacts)
    new_ids = sorted(int(contact_id) for contact_id in phone_ids if contact_id is not None)

    if previous_ids == new_ids:
        return

    new_contacts = list(PersonContact.objects.filter(id__in=new_ids))
    display_prev = _format_phones_display(previous_contacts)
    display_new = _format_phones_display(new_contacts)

    if display_prev == display_new:
        return

    LogContractPhones.objects.create(
        object=contract,
        previous_phone=display_prev,
        current_phone=display_new,
        user=user,
        observation=None,
    )


def contract_bank_change(file, is_saving, user=None):
    
    found_contracts = []
    found_persons = []
    non_existent_contracts = []
    no_contracts = []
    no_bank_accounts = []
    errors = []
    direct_debit_token = ConfigProject.objects.get(token='direct_debit_token').value
    direct_debit = PaymentType.objects.get(token=direct_debit_token)
    contract_active_token = ConfigProject.objects.get(token='contract_active_token').value
    try:
        content = file.read()
        
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        
        lines = content.split('\n')
        total_lines = len(lines)
        for line_number, line in enumerate(lines[2:], start=3):
            if line_number >= total_lines - 2:
                continue
            if not line.strip():
                continue
            
            if len(line) < 110:
                errors.append(f"Line {line_number}: Line too short (length: {len(line)})")
                continue
            
            contract_token = line[39:55].strip()        # OR PERSON TOKEN
            print("contract_token: ", contract_token)
            swift_code = line[74:85].strip()
            bank_account = line[85:110].strip()
            bank_code = bank_account[4:8]
            
            if not contract_token:
                no_contracts.append({
                    'line': line_number,
                    'contract_token': contract_token
                })
            
            
            
            contract_tokens = [
                contract_token, 
                contract_token[1:-3] + '/' + contract_token[-3:],
                contract_token[1:9] + '/' + contract_token[9:12],
                ]
            print("contract_tokens: ", contract_tokens)
            
            contract = None
            person = None
            if bank_code:
                try:
                    bank = Bank.objects.get(token__in=get_spanish_bank_code_candidates(bank_code))
                except Exception as e:
                    bank = None
            try:
                country = Country.objects.get(iso_code=bank_account[:2])
            except Exception as e:
                country = Country.objects.get(is_default=True)
                
            if contract_token:
                try:
                    contract = Contract.objects.get(token__in=contract_tokens)
                    if is_saving:
                        
                        current_holder_bank = (
                            contract.payment.IBAN.person 
                            if contract.payment and contract.payment.IBAN and contract.payment.IBAN.person
                            else contract.holder
                        )
                            
                        new_person_bank = _get_new_person_bank(current_holder_bank, bank_account, bank, country, swift_code)
                        
                        _update_contract_payment(contract, new_person_bank, direct_debit, direct_debit_token, user)
                            
                    if not bank_account:
                        no_bank_accounts.append({
                            'line': line_number,
                            'contract_token': contract_token,
                            
                        })
                    else:
                        print("contract: ", contract.token)
                        found_contracts.append({
                            'contract_id': contract.id,
                            'contract_token': contract.token,
                            'bank_account': bank_account,
                            'current_bank_account': contract.payment.IBAN.iban if contract.payment and contract.payment.IBAN else None,
                            'swift_code': swift_code,
                            'bank_name': bank.name,
                            'line': line_number
                        })
                    
                except Exception as e:
                    pass
                
                if not contract:
                    try:
                        person = Person.objects.get(token=contract_token)
                        person_contracts = Contract.objects.filter(
                            Q(holder=person) | Q(owner=person) | Q(tenant=person) |
                            Q(payment__IBAN__person=person)
                        ).filter(status__token=contract_active_token).distinct()
                        contracts_payment = Contract.objects.filter(payment__IBAN__person=person,status__token=contract_active_token)
                        person_contracts_without_payment = person_contracts.exclude(id__in=contracts_payment.values_list('id', flat=True))
                        for person_contract in contracts_payment:
                            found_contracts.append({
                                'contract_id': person_contract.id,
                                'contract_token': person_contract.token,
                                'bank_account': bank_account,
                                'current_bank_account': person_contract.payment.IBAN.iban if person_contract.payment and person_contract.payment.IBAN else None,
                                'swift_code': swift_code,
                                'bank_name': bank.name,
                                'line': line_number
                            })
                        if is_saving:
                            new_person_bank = _get_new_person_bank(person, bank_account, bank, country, swift_code)
                            for person_contract in contracts_payment:
                                _update_contract_payment(person_contract, new_person_bank, direct_debit, direct_debit_token, user)
                        person_has_bank_account = False
                        person_banks = PersonBank.objects.filter(person=person)
                        for person_bank in person_banks:
                            if person_bank.iban == bank_account:
                                person_has_bank_account = True
                                break
                        if not bank_account:
                            no_bank_accounts.append({
                                'line': line_number,
                                'contract_token': contract_token,
                            })
                        else:
                            found_persons.append({
                                'person_id': person.id,
                                'person_token': person.token,
                                'person_name': f"{person.name} {person.surname if person.surname else ''}",
                                'already_has_bank_account': person_has_bank_account,
                                'contract_no_sepa': person_contracts_without_payment.count(),
                                'bank_account': bank_account,
                                'swift_code': swift_code,
                                'line': line_number
                            })
                    except Exception as e:
                        person = None
            
            if not contract and not person:
                non_existent_contracts.append({
                    'contract_token': contract_token,
                    'bank_account': bank_account,
                    'swift_code': swift_code if swift_code else None,
                    'bank_name': bank.name if bank else None,
                })

        ordered_found_persons = sorted(found_persons, key=lambda x: x['contract_no_sepa'], reverse=True)        
        
        return {
            'success': True,
            'found_contracts': found_contracts,
            'found_persons': ordered_found_persons,
            'non_existent_contracts': non_existent_contracts,
            'no_contracts': no_contracts,
            'no_bank_accounts': no_bank_accounts,
            'total_processed': len(found_contracts),
            'total_errors': len(errors)
        }
        
    except Exception as e:
        raise Exception(f"Error: {e}")
        return {
            'success': False,
            'non_existent_contracts': [],
            'no_contracts': [],
            'no_bank_accounts': [],
            'total_processed': 0,
            'total_errors': 0
        }

def _update_contract_payment(contract, new_person_bank, direct_debit, direct_debit_token, user=None):
    try:
        ContractDataChange.objects.create(
            contract=contract,
            previous_payment=contract.payment.IBAN if contract.payment and contract.payment.IBAN else None,
            current_payment=new_person_bank,
            new_payment_type=direct_debit,
            previous_payment_type=contract.payment.type if contract.payment and contract.payment.type else None,
            user=user,
        )
    except Exception as e:
        pass
    if contract.payment:
        if contract.payment.type.token != direct_debit_token:
            contract.payment.type = direct_debit
        contract.payment.IBAN = new_person_bank
        contract.payment.save()
    else:
        contract.payment = GeneralPayment.objects.create(
            token=f"{contract.token}_{new_person_bank.token}",
            type=direct_debit,
            IBAN=new_person_bank,
        )
        contract.save()

def _get_new_person_bank(person, bank_account, bank, country, swift_code):
    person_banks_queryset = PersonBank.objects.filter(person=person)
    person_bank_count = person_banks_queryset.count()
    person_banks_queryset.update(is_default=False)
    
    existing_person_bank = person_banks_queryset.filter(iban=bank_account).first()
    if existing_person_bank:
        existing_person_bank.is_default = True
        existing_person_bank.save()
        new_person_bank = existing_person_bank
    else:
        new_person_bank = PersonBank.objects.create(
            token=f"{person.token}_{person_bank_count + 1}",
            person=person,
            bank=bank,
            country=country,
            name=f"{person.name} {person.surname if person.surname else ''}",
            role="TITULAR",
            dni=person.token,
            account_number=bank_account,
            swift=swift_code,
            is_default=True,
            iban=bank_account,
        )
    
    return new_person_bank