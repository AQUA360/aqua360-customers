import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import F
from coredata.models import ConfigProject
from service.models import Meter, MeterStatus, SupplyPoint
from service.utils.supply_point_service import supply_point_change_meter  # ajusta l'import real si cal
from billing.models import EstimatedBag, Reading, EstimatedBagMovement
from logger.models import LogSupplyPointChange


METER_CHANGE_ORIGIN = 'Canvi de comptador'
# Valor antic (token cru) amb què el flux d'ordres desava l'origen.
LEGACY_ORDER_CHANGE_METER_ORIGIN = 'order_change_meter'


def to_decimal(value):
    """Valor de lectura/consum com a Decimal (buit o no numèric => 0), sense perdre decimals."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return Decimal(0)
    try:
        return Decimal(str(value).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def add_to_estimated_bag(bag_id, amount):
    """
    Suma (o resta, amb amount negatiu) al saldo de la bossa d'estimades amb una
    expressió de BD, perquè dues actualitzacions simultànies no se sobreescriguin.
    """
    EstimatedBag.objects.filter(id=bag_id).update(
        total_consumption=F('total_consumption') + amount
    )


def get_previous_meter_reading(contract, supply_point, meter, date, exclude_id=None):
    """
    Última lectura vàlida del mateix comptador per al contracte i punt de
    subministrament, amb data <= `date`. El consum s'ha de calcular sempre
    contra lectures del mateix aparell físic, mai contra les d'un altre comptador.
    """
    qs = Reading.objects.filter(
        contract=contract,
        supply_point=supply_point,
        meter=meter,
        is_control=False,
        is_active=True,
        reading_date__lte=date,
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return qs.order_by('-reading_date', '-id').first()


def compute_meter_consumption(reading_value, contract, supply_point, meter, date, exclude_id=None):
    """
    Consum d'una lectura respecte de l'anterior lectura del mateix comptador.
    Sense lectura anterior (comptador nou al contracte) el consum és 0.
    """
    previous = get_previous_meter_reading(contract, supply_point, meter, date, exclude_id)
    if not previous:
        return Decimal(0)
    return max(Decimal(0), to_decimal(reading_value) - to_decimal(previous.reading_value))


class MeterAssignedElsewhereError(Exception):
    """El comptador nou és a un altre punt de subministrament i no s'ha confirmat moure'l."""

    def __init__(self, assignments):
        super().__init__("Meter assigned to another supply point")
        self.assignments = assignments


METER_ASSIGNED_MESSAGE = (
    "El comptador ja és a un altre punt de subministrament. "
    "Cal confirmar que se'l vol treure d'aquell punt."
)


def meter_assigned_response_data(assignments):
    """Cos de la resposta 409 quan cal confirmar que es mou el comptador."""
    return {
        'error': METER_ASSIGNED_MESSAGE,
        'code': 'meter_assigned',
        'assignments': assignments,
    }


def is_reassign_confirmed(value):
    """`confirm_reassign` d'una petició: només un sí explícit confirma (un text "false" no)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    return isinstance(value, str) and value.strip().lower() in ('true', '1', 'yes', 't')


def lock_meter(meter_id):
    """
    Carrega el comptador bloquejant-ne la fila fins al final de la transacció:
    les assignacions del mateix comptador van en sèrie i la segona veu la primera
    (i retorna el 409) en lloc de treure-li el comptador sense avís.
    """
    return Meter.objects.select_for_update().get(id=meter_id)


def get_meter_assignments_elsewhere(meter, supply_point_id=None):
    """
    Punts de subministrament (diferents de `supply_point_id`) on és ara el
    comptador, amb els contractes actius de cadascun. Un comptador general pot
    ser a diversos punts alhora: no compta com a assignat.
    """
    if meter is None or meter.is_general:
        return []
    supply_points = SupplyPoint.objects.filter(meter=meter).select_related('address')
    if supply_point_id:
        supply_points = supply_points.exclude(id=supply_point_id)
    active_contract_token = ConfigProject.objects.get(token='contract_active_token').value

    assignments = []
    for supply_point in supply_points.order_by('id'):
        contracts = supply_point.contracts.filter(
            status__token=active_contract_token,
        ).select_related('holder').order_by('id')
        assignments.append({
            'supply_point_id': supply_point.id,
            'supply_point_token': supply_point.token,
            'address': str(supply_point.address) if supply_point.address_id else None,
            'contracts': [
                {
                    'id': contract.id,
                    'token': contract.token,
                    'holder': (
                        ' '.join(filter(None, [contract.holder.name, contract.holder.surname]))
                        if contract.holder_id else None
                    ),
                }
                for contract in contracts
            ],
        })
    return assignments


def release_meter_from_other_supply_points(user, meter, target_supply_point):
    """
    Treu el comptador dels altres punts on era i deixa constància del canvi
    a l'historial de cadascun (no només al punt on s'assigna).
    """
    if meter.is_general:
        return
    others = list(SupplyPoint.objects.filter(meter=meter).exclude(id=target_supply_point.id))
    if not others:
        return
    SupplyPoint.objects.filter(id__in=[sp.id for sp in others]).update(meter=None)
    for supply_point in others:
        LogSupplyPointChange.objects.create(
            supply_point=supply_point,
            user=user,
            action='meter',
            field_changed='meter',
            previous_value=meter.code,
            current_value=None,
            previous_related_id=meter.id,
            current_related_id=None,
            observation=f"Comptador retirat per assignar-lo al punt {target_supply_point.token}",
        )


def set_meter_change_dates(new_meter, released_meter, change_date):
    """
    Desa la data del canvi com a data d'instal·lació del comptador nou i de
    desinstal·lació del comptador retirat, només si encara no en tenen.
    `released_meter` és el comptador vell quan ja no és a cap punt de subministrament.
    """
    if not isinstance(change_date, datetime.date):
        return
    if not new_meter.installation_at:
        new_meter.installation_at = change_date
        new_meter.save(update_fields=['installation_at'])
    if released_meter and not released_meter.uninstallation_at:
        released_meter.uninstallation_at = change_date
        released_meter.save(update_fields=['uninstallation_at'])


class MeterChangeService:
    """
    Encapsula el canvi de comptador d'un punt de subministrament: mou el meter
    actiu al supply_point, tanca/activa estats, i crea les lectures de tancament
    i inicial per a cada contracte actiu del punt.

    Extret de SupplyPointViewSet.save_meter_change (service/views/supply_point_view.py)
    per fer-lo reutilitzable des de: la UI normal, el flux GOT/canvi de comptador
    via ordre de treball, i el consumidor RabbitMQ/GMAO.
    """

    def __init__(self, user, order_report=None):
        self.user = user
        self.order_report = order_report  # per deixar procedència a Reading, si el camp existeix

    @transaction.atomic
    def apply(self, supply_point_id, prev_meter_id, new_meter_id, origin,
              change_date, previous_reading_data, new_reading_data,
              confirm_reassign=False):
        """
        Sense `confirm_reassign`, si el comptador nou és a un altre punt no es
        fa res i es llança MeterAssignedElsewhereError amb on és.
        """

        if isinstance(change_date, str):
            try:
                change_date = datetime.datetime.strptime(change_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        if change_date is None:
            change_date = datetime.date.today()

        current_meter = Meter.objects.get(id=prev_meter_id) if prev_meter_id else None
        new_meter = lock_meter(new_meter_id)

        active_contract_token = ConfigProject.objects.get(token='contract_active_token').value
        meter_status_active_token = ConfigProject.objects.get(token='meter_status_active_token').value
        meter_status_inactive_token = ConfigProject.objects.get(token='meter_status_inactive_token').value
        meter_status_active = MeterStatus.objects.get(token=meter_status_active_token)
        meter_status_inactive = MeterStatus.objects.get(token=meter_status_inactive_token)

        supply_point = SupplyPoint.objects.get(id=supply_point_id)

        if not confirm_reassign:
            assignments = get_meter_assignments_elsewhere(new_meter, supply_point.id)
            if assignments:
                raise MeterAssignedElsewhereError(assignments)
        release_meter_from_other_supply_points(self.user, new_meter, supply_point)

        supply_point.meter = new_meter
        supply_point.save()

        if new_meter.status.token != meter_status_active_token:
            new_meter.status = meter_status_active
            new_meter.save()

        released_meter = None
        if current_meter:
            if not SupplyPoint.objects.filter(meter=current_meter).exists():
                current_meter.status = meter_status_inactive
                current_meter.save()
                released_meter = current_meter

        set_meter_change_dates(new_meter, released_meter, change_date)

        supply_point_change_meter(self.user, supply_point.id, current_meter, new_meter)

        if current_meter:
            self._create_meter_reading(
                current_meter, previous_reading_data, change_date, supply_point,
                origin, active_contract_token,
            )
        self._create_meter_reading(
            new_meter, new_reading_data, change_date, supply_point,
            origin, active_contract_token,
        )

        return supply_point

    def _create_meter_reading(self, meter, reading_data, date, supply_point, origin, active_contract_token):
        supply_point_contracts = supply_point.contracts.filter(status__token=active_contract_token)
        for contract in supply_point_contracts:
            contract_prev_reading = Reading.objects.filter(
                contract=contract,
                supply_point=supply_point,
                is_control=False,
                is_active=True,
                reading_date__lte=date,
            ).order_by('-reading_date', '-id').first()

            try:
                estimated_bag = contract.estimated_bags.filter(supply_point=supply_point).first()
            except Exception:
                estimated_bag = None

            # Lectura buida => 0 (lectura inicial per defecte), però s'accepta
            # qualsevol valor inicial diferent de 0.
            reading_value = to_decimal(reading_data.get('reading_value'))

            if reading_data.get('calculated_value') is not None:
                calculated_value = to_decimal(reading_data['calculated_value'])
            else:
                calculated_value = compute_meter_consumption(
                    reading_value, contract, supply_point, meter, date,
                )
            consumption_days = (date - contract_prev_reading.reading_date).days if contract_prev_reading else 0
            # Consum estimat ja compensat (i descomptat de la bossa) per la lectura fusionada.
            merged_estimated_used = Decimal(0)

            if (
                contract_prev_reading
                and contract_prev_reading.invoices.count() == 0
                and contract_prev_reading.previous_reading
                and not contract_prev_reading.is_control
                and not contract_prev_reading.is_close
                and not contract_prev_reading.previous_reading.is_close
            ):
                calculated_value = to_decimal(contract_prev_reading.calculated_value) + calculated_value
                merged_estimated_used = to_decimal(contract_prev_reading.estimated_used)
                consumption_days = int(consumption_days or 0) + int(contract_prev_reading.consumption_days or 0)
                contract_prev_reading.is_control = True
                contract_prev_reading.save()
                contract_prev_reading = contract_prev_reading.previous_reading

            # real_consumption es calcula sobre el calculated_value final, tant
            # si s'ha fusionat amb la lectura anterior com si no.
            # Si s'ha fusionat, només es descompta de la bossa el consum pendent
            # que la lectura anterior no havia compensat ja.
            additional_estimated = Decimal(0)
            pending_consumption = max(Decimal(0), calculated_value - merged_estimated_used)
            if estimated_bag and to_decimal(estimated_bag.total_consumption) > 0:
                additional_estimated = min(to_decimal(estimated_bag.total_consumption), pending_consumption)
            used_estimated = (merged_estimated_used + additional_estimated) or None
            real_consumption = calculated_value - (used_estimated or Decimal(0))

            reading_kwargs = dict(
                supply_point=supply_point,
                contract=contract,
                meter=meter,
                reading_date=date,
                reading_value=reading_data.get('reading_value') or 0,
                calculated_value=calculated_value,
                consumption_days=consumption_days,
                is_close=reading_data.get('is_close'),
                origin=origin,
                leak_value=reading_data.get('leak_value'),
                real_consumption=real_consumption,
                estimated_used=used_estimated,
                previous_reading=contract_prev_reading,
            )
            # Si el model Reading té el camp order_report (afegit per procedència
            # del canvi de comptador via ordre de treball), l'omplim.
            if self.order_report is not None and hasattr(Reading, 'order_report'):
                reading_kwargs['order_report'] = self.order_report

            reading = Reading.objects.create(**reading_kwargs)

            if additional_estimated > 0:
                EstimatedBagMovement.objects.create(
                    amount=additional_estimated,
                    estimated_bag=estimated_bag,
                    reading=reading,
                    movement_date=date,
                    is_positive=False
                )
                add_to_estimated_bag(estimated_bag.id, -additional_estimated)