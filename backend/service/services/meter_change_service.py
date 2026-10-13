import datetime
from django.db import transaction
from coredata.models import ConfigProject
from service.models import Meter, MeterStatus, SupplyPoint
from service.utils.supply_point_service import supply_point_change_meter  # ajusta l'import real si cal
from billing.models import Reading, EstimatedBagMovement


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
              change_date, previous_reading_data, new_reading_data):

        if isinstance(change_date, str):
            try:
                change_date = datetime.datetime.strptime(change_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        if change_date is None:
            change_date = datetime.date.today()

        current_meter = Meter.objects.get(id=prev_meter_id) if prev_meter_id else None
        new_meter = Meter.objects.get(id=new_meter_id)

        active_contract_token = ConfigProject.objects.get(token='contract_active_token').value
        meter_status_active_token = ConfigProject.objects.get(token='meter_status_active_token').value
        meter_status_inactive_token = ConfigProject.objects.get(token='meter_status_inactive_token').value
        meter_status_active = MeterStatus.objects.get(token=meter_status_active_token)
        meter_status_inactive = MeterStatus.objects.get(token=meter_status_inactive_token)

        if not new_meter.is_general:
            SupplyPoint.objects.filter(meter=new_meter).update(meter=None)

        supply_point = SupplyPoint.objects.get(id=supply_point_id)
        supply_point.meter = new_meter
        supply_point.save()

        if new_meter.status.token != meter_status_active_token:
            new_meter.status = meter_status_active
            new_meter.save()

        if current_meter:
            if not SupplyPoint.objects.filter(meter=current_meter).exists():
                current_meter.status = meter_status_inactive
                current_meter.save()

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
                reading_date__lte=date,
            ).order_by('-reading_date').first()

            try:
                estimated_bag = contract.estimated_bags.filter(supply_point=supply_point).first()
            except Exception:
                estimated_bag = None

            reading_value = int(reading_data.get('reading_value') or 0)

            if reading_data.get('calculated_value') is not None:
                calculated_value = int(reading_data['calculated_value'])
            elif contract_prev_reading:
                calculated_value = max(
                    0,
                    reading_value - int(contract_prev_reading.reading_value or 0)
                )
            else:
                calculated_value = 0
            consumption_days = (date - contract_prev_reading.reading_date).days if contract_prev_reading else 0

            if (
                contract_prev_reading
                and contract_prev_reading.invoices.count() == 0
                and contract_prev_reading.previous_reading
                and not contract_prev_reading.is_control
                and not contract_prev_reading.is_close
                and not contract_prev_reading.previous_reading.is_close
            ):
                calculated_value = int(contract_prev_reading.calculated_value) + int(calculated_value)
                consumption_days = int(consumption_days or 0) + int(contract_prev_reading.consumption_days or 0)
                contract_prev_reading.is_control = True
                contract_prev_reading.save()
                contract_prev_reading = contract_prev_reading.previous_reading

            used_estimated = None
            if estimated_bag and estimated_bag.total_consumption > 0:
                used_estimated = estimated_bag.total_consumption if estimated_bag.total_consumption < calculated_value else calculated_value

            reading_kwargs = dict(
                supply_point=supply_point,
                contract=contract,
                meter=meter,
                reading_date=date,
                reading_value=reading_data.get('reading_value'),
                calculated_value=calculated_value,
                consumption_days=consumption_days,
                is_close=reading_data.get('is_close'),
                origin=origin,
                leak_value=reading_data.get('leak_value'),
                real_consumption=int(calculated_value) - int(used_estimated or 0),
                estimated_used=used_estimated,
                previous_reading=contract_prev_reading,
            )
            # Si el model Reading té el camp order_report (afegit per procedència
            # del canvi de comptador via ordre de treball), l'omplim.
            if self.order_report is not None and hasattr(Reading, 'order_report'):
                reading_kwargs['order_report'] = self.order_report

            reading = Reading.objects.create(**reading_kwargs)

            if used_estimated and used_estimated > 0:
                EstimatedBagMovement.objects.create(
                    amount=used_estimated,
                    estimated_bag=estimated_bag,
                    reading=reading,
                    movement_date=date,
                    is_positive=False
                )
                estimated_bag.total_consumption -= used_estimated
                estimated_bag.save()