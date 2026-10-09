from django.core.management.color import color_style

from billing.models import Reading
from contract.models import Contract

style = color_style()

METER_CHANGE_ORIGIN = 'Canvi de comptador'
MODIFICACIO_ORIGIN = 'Modificació'
READINGS_TO_FIX = 5
LOOKBACK_WINDOW = 20


def _find_previous(reading, candidates):
    """
    candidates ve ordenat de mes recent a mes antic i nomes conte lectures
    amb reading_date <= reading.reading_date (la propia lectura exclosa).

    Normalment la lectura anterior "correcta" es la mes recent del mateix
    comptador (per no barrejar lectures de dos aparells fisics diferents).
    L'unica excepcio es la primera lectura d'un comptador nou arran d'un
    canvi (reading_value=0), que si ha d'enllaçar amb la ultima lectura del
    comptador vell encara que sigui un aparell diferent -- es precisament
    aixo el que marca el canvi de comptador.
    """
    if not candidates:
        return None

    if reading.reading_value == 0:
        return candidates[0]

    for candidate in candidates:
        if candidate.meter_id == reading.meter_id:
            return candidate

    return candidates[0]


def _build_contract_plan(contract_id):
    """
    Agafa les READINGS_TO_FIX lectures mes recents (actives) del contracte,
    calcula quina hauria de ser previous_reading/consumption_days/
    calculated_value de cadascuna i comprova si la 4a lectura (la primera
    anterior al canvi de comptador) te factura.
    """
    window = list(
        Reading.objects
        .filter(contract_id=contract_id, is_active=True)
        .order_by('-reading_date', '-id')[:LOOKBACK_WINDOW]
    )
    readings = window[:READINGS_TO_FIX]

    # Si alguna de les lectures que toquem es una "Modificació", l'historial
    # ja ha estat corregit a ma i encadenar-la automaticament es arriscat
    # (p. ex. una Modificació del mateix dia que el canvi
    # de comptador que un algorisme purament cronologic pot enllaçar amb el
    # comptador equivocat). En aquest cas no toquem res del contracte i el
    # deixem per revisar manualment.
    needs_manual_review = any(reading.origin == MODIFICACIO_ORIGIN for reading in readings)

    changes = []
    for i, reading in enumerate(readings if not needs_manual_review else []):
        previous = _find_previous(reading, window[i + 1:])
        # Si no trobem cap candidata (nomes pot passar si el contracte no te
        # prou historial dins la finestra), no toquem res: mantenim la
        # previous_reading/consumption_days/calculated_value que ja tenia.
        previous_to_assign = previous if previous is not None else reading.previous_reading

        consumption_days = reading.consumption_days
        calculated_value = reading.calculated_value

        if previous and reading.reading_date is not None and previous.reading_date is not None:
            consumption_days = (reading.reading_date - previous.reading_date).days

        if previous and reading.reading_value is not None and previous.reading_value is not None:
            if previous.meter_id != reading.meter_id:
                # Lectura del costat d'un canvi fisic de comptador: no te sentit
                # restar el valor de dos aparells diferents. Es el mateix criteri
                # que ja segueixen totes les lectures d'aquest tipus que no estan
                # trencades en aquesta mateixa taula.
                calculated_value = 0
            else:
                calculated_value = reading.reading_value - previous.reading_value

        changes.append({
            'reading': reading,
            'previous': previous,
            'previous_to_assign': previous_to_assign,
            'old_previous_reading_id': reading.previous_reading_id,
            'old_is_control': reading.is_control,
            'old_consumption_days': reading.consumption_days,
            'new_consumption_days': consumption_days,
            'old_calculated_value': reading.calculated_value,
            'new_calculated_value': calculated_value,
        })

    fourth_reading = None
    fourth_has_invoice = None
    if not needs_manual_review and len(readings) >= 4:
        fourth_reading = readings[3]
        fourth_has_invoice = fourth_reading.invoices.exists()

    return {
        'contract_id': contract_id,
        'readings': readings,
        'changes': changes,
        'needs_manual_review': needs_manual_review,
        'fourth_reading': fourth_reading,
        'fourth_has_invoice': fourth_has_invoice,
        'incomplete': len(readings) < READINGS_TO_FIX,
    }


def _print_plan(plan):
    contract = Contract.objects.filter(id=plan['contract_id']).first()
    contract_label = contract.token if contract and contract.token else plan['contract_id']
    print(f"\nContract {contract_label} (id={plan['contract_id']})")

    if plan['incomplete']:
        print(style.WARNING(
            f"  Only {len(plan['changes'])} active readings found for this contract (expected {READINGS_TO_FIX})"
        ))

    for i, change in enumerate(plan['changes'], start=1):
        reading = change['reading']
        previous = change['previous']
        previous_to_assign = change['previous_to_assign']

        prev_change = (
            f"{change['old_previous_reading_id']} -> {previous_to_assign.id if previous_to_assign else None}"
            if change['old_previous_reading_id'] != (previous_to_assign.id if previous_to_assign else None)
            else f"{change['old_previous_reading_id']} (unchanged)"
        )
        control_change = (
            f"{change['old_is_control']} -> False"
            if change['old_is_control']
            else "False (unchanged)"
        )
        days_change = (
            f"{change['old_consumption_days']} -> {change['new_consumption_days']}"
            if change['old_consumption_days'] != change['new_consumption_days']
            else f"{change['old_consumption_days']} (unchanged)"
        )
        value_change = (
            f"{change['old_calculated_value']} -> {change['new_calculated_value']}"
            if change['old_calculated_value'] != change['new_calculated_value']
            else f"{change['old_calculated_value']} (unchanged)"
        )

        flag = ""
        if previous is None:
            flag = style.ERROR("  [!] no earlier reading available, previous_reading/consumption_days/calculated_value left untouched")

        print(
            f"  [{i}] reading {reading.id} | {reading.reading_date} | origin={reading.origin!r} | "
            f"value={reading.reading_value} | meter={reading.meter_id}"
        )
        print(f"       previous_reading: {prev_change}")
        print(f"       is_control: {control_change}")
        print(f"       consumption_days: {days_change}")
        print(f"       calculated_value: {value_change}")
        if flag:
            print(flag)

    if plan['fourth_reading'] is None:
        print(style.WARNING("  4th reading not available (fewer than 4 active readings), skipping invoice check"))
    else:
        fourth = plan['fourth_reading']
        if plan['fourth_has_invoice']:
            print(f"  4th reading ({fourth.id}, {fourth.reading_date}) has an invoice related: OK")
        else:
            print(style.ERROR(f"  4th reading ({fourth.id}, {fourth.reading_date}) has NO invoice related"))


def run(dry_run=False):
    matched_readings = Reading.objects.filter(
        origin=METER_CHANGE_ORIGIN,
        is_control=True,
        is_active=True,
        contract__isnull=False,
    )
    contract_ids = sorted(set(matched_readings.values_list('contract_id', flat=True)))

    print(f"Found {matched_readings.count()} readings with origin={METER_CHANGE_ORIGIN!r} and is_control=True")
    print(f"Affecting {len(contract_ids)} distinct contracts")

    readings_to_update = []
    incomplete_contracts = []
    contracts_missing_invoice = []
    manual_review_contracts = []

    for contract_id in contract_ids:
        plan = _build_contract_plan(contract_id)

        if plan['needs_manual_review']:
            contract = Contract.objects.filter(id=contract_id).first()
            contract_label = contract.token if contract and contract.token else contract_id
            print(style.WARNING(
                f"Contract {contract_label} (id={contract_id}): has a {MODIFICACIO_ORIGIN!r} reading "
                f"among the ones being checked -- left untouched, check manually"
            ))
            manual_review_contracts.append(contract_label)
            continue

        if dry_run:
            _print_plan(plan)

        if plan['incomplete']:
            incomplete_contracts.append(contract_id)

        for change in plan['changes']:
            reading = change['reading']
            reading.previous_reading = change['previous_to_assign']
            reading.is_control = False
            reading.consumption_days = change['new_consumption_days']
            reading.calculated_value = change['new_calculated_value']
            readings_to_update.append(reading)

        if plan['fourth_reading'] is not None and not plan['fourth_has_invoice']:
            contracts_missing_invoice.append(contract_id)

    print("\n----- Summary -----")
    print(f"Contracts processed: {len(contract_ids)}")
    print(f"Readings to update: {len(readings_to_update)}")
    if incomplete_contracts:
        print(style.WARNING(
            f"Contracts with fewer than {READINGS_TO_FIX} active readings: {len(incomplete_contracts)} -> {incomplete_contracts}"
        ))
    if manual_review_contracts:
        print(style.WARNING(
            f"Contracts left untouched because of a {MODIFICACIO_ORIGIN!r} reading: "
            f"{len(manual_review_contracts)} -> {manual_review_contracts}"
        ))
    print(f"Contracts where the 4th reading has NO invoice related: {len(contracts_missing_invoice)}")
    if contracts_missing_invoice:
        print(f"  -> {contracts_missing_invoice}")

    if dry_run:
        print(style.WARNING("\nDRY RUN: no changes have been saved."))
        return

    Reading.objects.bulk_update(
        readings_to_update,
        ['previous_reading', 'is_control', 'consumption_days', 'calculated_value'],
        batch_size=500,
    )
    print(style.SUCCESS(f"\nUpdated {len(readings_to_update)} readings across {len(contract_ids)} contracts"))
