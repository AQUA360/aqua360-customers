# services/utils/supply_point_service.py
import datetime
from decimal import Decimal, InvalidOperation

from logger.models import LogSupplyPointChange
from ..models import SupplyPoint, SupplyPointMeterHistory, SupplyPointStatus
from coredata.models import ConfigProject

def supply_point_activate(user, supply_point_id):
    supply_point = SupplyPoint.objects.get(id=supply_point_id)
    previous_status = supply_point.status
    activate_token = ConfigProject.objects.get(token='supply_point_status_activate_token').value
    if activate_token == None:
        activate_token = 'active'
    supply_point.status = SupplyPointStatus.objects.get(token=activate_token)
    supply_point.removal_at = None
    supply_point.removal_reason = None
    supply_point.save()
    
    # logger
    LogSupplyPointChange.objects.create(
        supply_point=supply_point,
        user=user,
        action='activate',
        field_changed='status',
        previous_value=previous_status.name,
        current_value=supply_point.status.name,
        previous_related_id=previous_status.id,
        current_related_id=supply_point.status.id
    )

    
    return supply_point


def supply_point_deactivate(user, supply_point_id, date, reason):
    supply_point = SupplyPoint.objects.get(id=supply_point_id)
    previous_status = supply_point.status
    deactivate_token = ConfigProject.objects.get(token='supply_point_status_deactivate_token').value
    if deactivate_token == None:
        deactivate_token = '-1'
    supply_point.status = SupplyPointStatus.objects.get(token=deactivate_token)
    supply_point.removal_at = date
    supply_point.removal_reason = reason
    supply_point.save()
    
    # logger
    LogSupplyPointChange.objects.create(
        supply_point=supply_point,
        user=user,
        action='deactivate',
        field_changed='status',
        previous_value=previous_status.name,
        current_value=supply_point.status.name,
        previous_related_id=previous_status.id,
        current_related_id=supply_point.status.id,
        observation=reason
    )

    return supply_point


def _to_reading_value(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def supply_point_change_meter(user, supply_point_id, previous_meter, current_meter,
                              change_date=None, old_reading=None, new_reading=None,
                              source='other', order=None, observation=None):
    """
    Deixa constància d'un canvi de comptador d'un punt: al log genèric
    (LogSupplyPointChange) i a l'historial de comptadors (SupplyPointMeterHistory).
    """
    supply_point = SupplyPoint.objects.get(id=supply_point_id)
    if user is not None and getattr(user, 'is_anonymous', False):
        user = None

    # logger
    LogSupplyPointChange.objects.create(
        supply_point=supply_point,
        user=user,
        action='meter',
        field_changed='meter',
        previous_value=previous_meter.code if previous_meter else None,
        current_value=current_meter.code if current_meter else None,
        previous_related_id=previous_meter.id if previous_meter else None,
        current_related_id=current_meter.id if current_meter else None,
        observation=observation
    )

    if not isinstance(change_date, datetime.date):
        change_date = datetime.date.today()

    SupplyPointMeterHistory.objects.create(
        supply_point=supply_point,
        old_meter=previous_meter,
        new_meter=current_meter,
        change_date=change_date,
        old_reading=_to_reading_value(old_reading),
        new_reading=_to_reading_value(new_reading),
        source=source,
        order=order,
        user=user,
        observation=observation,
    )

    return supply_point

def supply_point_change_connection(user, supply_point_id, previous_connection, current_connection):
    supply_point = SupplyPoint.objects.get(id=supply_point_id)
    
    # logger
    LogSupplyPointChange.objects.create(
        supply_point=supply_point,
        user=user,
        action='connection',
        field_changed='connection',
        previous_value=previous_connection.token,
        current_value=current_connection.token,
        previous_related_id=previous_connection.id,
        current_related_id=current_connection.id,
        observation=None
    )

    return supply_point

def supply_point_change_property(user, supply_point_id, previous_property, current_property):
    supply_point = SupplyPoint.objects.get(id=supply_point_id)
    
    # logger
    LogSupplyPointChange.objects.create(
        supply_point=supply_point,
        user=user,
        action='property',
        field_changed='property',
        previous_value=previous_property.token if previous_property else None,
        current_value=current_property.token if current_property else None,
        previous_related_id=previous_property.id if previous_property else None,
        current_related_id=current_property.id if current_property else None,
        observation=None
    )

    return supply_point

def supply_point_change_address(user, supply_point_id, previous_address, current_address):
    supply_point = SupplyPoint.objects.get(id=supply_point_id)
    
    # logger
    LogSupplyPointChange.objects.create(
        supply_point=supply_point,
        user=user,
        action='address',
        field_changed='address',
        previous_value=previous_address,
        current_value=current_address,
        previous_related_id=None,
        current_related_id=None,
        observation=None
    )

    return supply_point