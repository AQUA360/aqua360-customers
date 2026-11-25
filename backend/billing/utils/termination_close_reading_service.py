"""Lectura de tancament d'una baixa vinculada a una alta (canvi de titular).

En un canvi de titular la lectura de tall s'acostuma a entrar a l'alta com a lectura
inicial (`request-reading/`). En finalitzar l'alta aquesta lectura passa al contracte nou,
però el contracte de sortida es quedava sense lectura de tancament i la baixa sense cap
lectura vinculada: la factura de baixa acabava agafant la darrera lectura del contracte
de sortida, encara que ja estigués facturada.

Aquí es crea, per a cada comptador que encara no en tingui, la lectura de tancament del
contracte de sortida a partir de la lectura inicial de l'alta (mateixa data i valor) i es
vincula a la baixa, igual que quan s'entra la lectura des de la pantalla de baixa.
"""
from billing.models import Reading


def _initial_readings(termination):
    """Lectures inicials (noves) de les altes actives vinculades a la baixa."""
    requests = termination.contract_requests_termination_requests.filter(is_active=True)
    readings = []
    for contract_request in requests:
        # "Facturar període complert": la inicial és una lectura del contracte de sortida
        # traspassada a l'alta, no una lectura de tall nova.
        if contract_request.bill_full_period:
            continue
        # Canvi de nom mantenint el codi: la lectura de tall es queda al contracte nou i es
        # factura al proper cicle (contract_service._rename_old_contract_and_get_reused_token).
        if contract_request.is_change_of_name and contract_request.keep_same_code:
            continue
        readings.extend(
            Reading.objects.filter(
                contract_request=contract_request,
                is_initial=True,
                is_control=False,
                reading_date__isnull=False,
                reading_value__isnull=False,
                meter__isnull=False,
                supply_point__isnull=False,
            ).select_related('meter').order_by('-reading_date', '-id')
        )
    return readings


def _contract_has_supply_point(contract, supply_point_id):
    return contract.supply_point_default_id == supply_point_id \
        or contract.supply_points.filter(id=supply_point_id).exists()


def ensure_termination_close_readings(termination):
    """Crea i vincula a la baixa les lectures de tancament que falten. Retorna les noves."""
    contract = termination.contract
    if not contract:
        return []

    created = []
    done_meters = set(
        termination.readings.filter(is_active=True, is_control=False).values_list('meter_id', flat=True)
    )
    for initial in _initial_readings(termination):
        if initial.meter_id in done_meters:
            continue
        # Canvi de nom mantenint el codi: la inicial ja és del mateix contracte.
        if initial.contract_id == contract.id:
            continue
        if not _contract_has_supply_point(contract, initial.supply_point_id):
            continue
        done_meters.add(initial.meter_id)

        contract_readings = Reading.objects.filter(
            contract=contract,
            supply_point_id=initial.supply_point_id,
            meter_id=initial.meter_id,
            is_active=True,
            is_control=False,
        )
        # Si el contracte de sortida ja té una lectura d'aquell dia, és la de tancament.
        same_day = contract_readings.filter(
            reading_date=initial.reading_date, is_initial=False,
        ).order_by('-id').first()
        if same_day:
            termination.readings.add(same_day)
            continue
        # Amb lectures posteriors al tall no és un tall normal: no s'inventa res.
        if contract_readings.filter(reading_date__gt=initial.reading_date).exists():
            continue

        previous = contract_readings.filter(
            reading_date__lt=initial.reading_date, reading_value__isnull=False,
        ).order_by('-reading_date', '-id').first()
        value = float(initial.reading_value)
        calculated = value - float(previous.reading_value) if previous else value
        reading = Reading.objects.create(
            token=f"{initial.meter.code or 'NOMETER'}/MANUAL",
            reading_date=initial.reading_date,
            reading_value=initial.reading_value,
            leak_value=initial.leak_value,
            origin='Manual',
            calculated_value=calculated,
            real_consumption=calculated,
            supply_point_id=initial.supply_point_id,
            meter_id=initial.meter_id,
            previous_reading=previous,
            consumption_days=(initial.reading_date - previous.reading_date).days if previous else 0,
            contract=contract,
            is_control=False,
            is_estimated=False,
            is_active=True,
        )
        termination.readings.add(reading)
        created.append(reading)
    return created
