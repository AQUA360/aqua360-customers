from django.db.models import F

from billing.models import Reading
from billing.utils.reading_filters import PENDING_READING_FILTER


# "Facturar període complert": quan el contracte anterior del punt de subministrament té
# una lectura encara no facturada (sense factura definitiva), es pot fer servir aquesta
# mateixa lectura com a lectura inicial de l'alta en lloc de crear-ne una de nova.
#
# Durant la sol·licitud la lectura es marca com a inicial de la ContractRequest i es
# desactiva (igual que les lectures inicials creades via `request-reading/`), però es manté
# el `contract` original. Així es pot distingir d'una lectura inicial nova (que té
# `contract` a null fins a finalitzar l'alta) i es pot retornar al contracte anterior si
# l'usuari acaba introduint una lectura inicial manual. En finalitzar l'alta,
# `contract_create()` la vincula al contracte nou.


def get_transferable_reading(contract_request, supply_point, meter):
    """Darrera lectura del contracte anterior al punt/comptador si encara no està facturada.

    Només es proposa la lectura MÉS RECENT del punt de subministrament. No es filtra per
    tipus abans d'agafar-la: si la més recent no es pot traspassar (de tancament, de control,
    inicial, estimada, d'un altre comptador, sense contracte o ja facturada) no es proposa cap
    lectura, en lloc de saltar-la i agafar-ne una de més antiga.
    """
    if not supply_point or not meter:
        return None
    last_reading = Reading.objects.filter(
        supply_point=supply_point,
        is_active=True,
    ).exclude(
        contract_request=contract_request,
    ).order_by(F('reading_date').desc(nulls_last=True), '-created_at', '-id').first()
    if not last_reading:
        return None
    if last_reading.meter_id != meter.id or not last_reading.contract_id:
        return None
    # Les lectures estimades porten moviments de bossa d'estimació lligats al contracte
    # anterior; no es traspassen.
    if last_reading.is_control or last_reading.is_initial or last_reading.is_close or last_reading.is_estimated:
        return None
    if not Reading.objects.filter(id=last_reading.id).filter(PENDING_READING_FILTER).exists():
        return None
    return last_reading


def restore_transferred_readings(contract_request, supply_point):
    """Retorna al seu contracte les lectures traspassades a la sol·licitud com a inicials."""
    Reading.objects.filter(
        contract_request=contract_request,
        supply_point=supply_point,
        is_initial=True,
        contract__isnull=False,
    ).update(contract_request=None, is_initial=False, is_active=True)


def transfer_reading_as_initial(contract_request, reading):
    # Una prefactura del contracte anterior que inclogui la lectura quedaria incoherent;
    # es desvincula (mateix criteri que en revertir un lot de lectures).
    for invoice in reading.invoices.filter(type_final='P'):
        invoice.readings.remove(reading)

    restore_transferred_readings(contract_request, reading.supply_point)
    Reading.objects.filter(
        contract_request=contract_request,
        supply_point=reading.supply_point,
        is_initial=True,
        contract__isnull=True,
    ).delete()

    reading.contract_request = contract_request
    reading.is_initial = True
    reading.is_active = False
    reading.save(update_fields=['contract_request', 'is_initial', 'is_active', 'updated_at'])
    return reading


def move_newer_readings_to_contract(contract_request, contract, initial_reading):
    """Passa al contracte nou les lectures posteriors a la lectura inicial.

    Si en l'alta es tria com a inicial una lectura antiga del comptador, totes les lectures
    posteriors (del mateix punt i comptador) corresponen ja al nou titular. Es fa en finalitzar
    l'alta (`contract_create()`), de manera que si la sol·licitud no s'acaba no es mou res.

    Només es mouen lectures dels contractes donats de baixa per aquesta sol·licitud (no les
    còpies d'altres contractes que comparteixen el comptador), ni de tancament ni inicials, i
    només les pendents de facturar: les que ja tenen factura definitiva es queden al contracte
    anterior. Retorna la llista de lectures mogudes.
    """
    if not initial_reading.meter_id or not initial_reading.reading_date:
        return []
    old_contract_ids = list(
        contract_request.contract_termination_requests.exclude(contract_id=contract.id)
        .values_list('contract_id', flat=True)
    )
    if not old_contract_ids:
        return []

    newer_readings = Reading.objects.filter(
        meter_id=initial_reading.meter_id,
        contract_id__in=old_contract_ids,
        reading_date__gt=initial_reading.reading_date,
        is_initial=False,
        is_close=False,
    ).filter(PENDING_READING_FILTER).exclude(id=initial_reading.id)
    if initial_reading.supply_point_id:
        newer_readings = newer_readings.filter(supply_point_id=initial_reading.supply_point_id)
    newer_readings = list(newer_readings.distinct().order_by('reading_date', 'id'))

    for reading in newer_readings:
        # Una prefactura del contracte anterior que inclogui la lectura quedaria incoherent;
        # es desvincula (mateix criteri que a transfer_reading_as_initial).
        for invoice in reading.invoices.filter(type_final='P'):
            invoice.readings.remove(reading)

    first_real = next((reading for reading in newer_readings if not reading.is_control), None)
    if first_real:
        # El consum no canvia (la inicial és una còpia de la lectura triada, amb el mateix
        # valor i data), però l'anterior ha de ser la inicial del contracte nou.
        first_real.previous_reading = initial_reading
        first_real.save(update_fields=['previous_reading', 'updated_at'])

    Reading.objects.filter(id__in=[reading.id for reading in newer_readings]).update(contract=contract)
    return newer_readings
