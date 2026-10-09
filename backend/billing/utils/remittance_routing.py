"""
Encaminament de remeses SEPA: decideix a quin compte de l'empresa emissora
(`CompanyBank`) va cada rebut, segons l'entitat bancària del PAGADOR.

El mapa el configura cada empresa a `service.models.CompanyBankRouting` (pàgina
d'empresa, pestanya d'encaminament de remeses). Aquí només s'aplica.
"""

from collections import defaultdict

from service.models import CompanyBank, CompanyBankRouting


def parse_payer_iban(iban):
    """
    Torna `(codi_pais, codi_entitat)` d'un IBAN de pagador.

    El codi d'entitat són els 4 dígits que segueixen el dígit de control i és el
    que `coredata.Bank.token` desa (p. ex. '2100' = CaixaBank). Només té sentit
    als IBAN espanyols; als estrangers l'entitat es torna buida i el que mana és
    el país.
    """
    if not iban:
        return None, None

    iban = str(iban).replace(' ', '').upper()
    if len(iban) < 4 or not iban[:2].isalpha():
        return None, None

    country = iban[:2]
    if country != 'ES' or len(iban) < 8:
        return country, None

    entity = iban[4:8]
    return country, entity if entity.isdigit() else None


def get_payment_company_id(payment_row):
    """
    Empresa emissora d'un rebut. Ve de la factura; els rebuts sense factura
    (compromisos i rebuts solts) pengen de l'empresa de la seva explotació.

    `payment_row` és un dict del `values()` de `build_payments_values()`.
    """
    return (
        payment_row.get('invoice__company_id')
        # Hi ha clients on `Invoice.company` està buit a quasi totes les
        # factures i l'única via és l'explotació que les va emetre.
        or payment_row.get('invoice__exploitation__company_id')
        or payment_row.get('commitment_deposit__contract__supply_point_default__connection__exploitation__company_id')
        or payment_row.get('contract__supply_point_default__connection__exploitation__company_id')
    )


def build_payments_values(payments):
    """
    Les dades mínimes per encaminar, en una sola consulta: no cal instanciar els
    `Payment` sencers per decidir-ne el compte.
    """
    return payments.values(
        'id',
        'payment_bank',
        'invoice__company_id',
        'invoice__exploitation__company_id',
        'commitment_deposit__contract__supply_point_default__connection__exploitation__company_id',
        'contract__supply_point_default__connection__exploitation__company_id',
    )


def get_company_routing_maps(company_ids):
    """
    Per cada empresa, el seu mapa d'encaminament ja resolt en diccionaris:
    `{company_id: {'banks': {bank_id: company_bank_id}, 'foreign': id, 'default': id}}`.
    """
    maps = defaultdict(lambda: {'banks': {}, 'foreign': None, 'default': None})

    routings = CompanyBankRouting.objects.filter(
        company_id__in=company_ids, is_active=True
    ).values('company_id', 'bank_id', 'company_bank_id', 'match_type')

    for routing in routings:
        company_map = maps[routing['company_id']]
        if routing['match_type'] == CompanyBankRouting.MATCH_PAYER_BANK:
            if routing['bank_id']:
                company_map['banks'][routing['bank_id']] = routing['company_bank_id']
        elif routing['match_type'] == CompanyBankRouting.MATCH_FOREIGN:
            company_map['foreign'] = routing['company_bank_id']
        elif routing['match_type'] == CompanyBankRouting.MATCH_DEFAULT:
            company_map['default'] = routing['company_bank_id']

    return maps


def get_company_fallback_banks(company_ids):
    """
    Compte de recanvi de cada empresa per quan el mapa no diu res, com a
    `{company_id: (company_bank_id, es_explicit)}`.

    És el marcat com a `is_default` i, si no n'hi ha cap, el primer compte SEPA
    actiu. Aquest segon cas és una tria arbitrària (mana l'id més baix) i per
    això es marca amb `es_explicit=False`: l'empresa hauria de tenir una fila
    `default` al mapa o un compte per defecte, i mentre no en tingui s'avisa.

    L'excepció és una empresa amb un sol compte: allà no hi ha res a triar ni a
    encaminar, i marcar-ho com a ambigu només generaria soroll.
    """
    fallbacks = {}
    counts = defaultdict(int)
    banks = CompanyBank.objects.filter(
        company_id__in=company_ids, is_active=True
    ).order_by('-is_default', '-is_sepa', 'id').values('id', 'company_id', 'is_default')

    for bank in banks:
        counts[bank['company_id']] += 1
        fallbacks.setdefault(bank['company_id'], (bank['id'], bool(bank['is_default'])))

    return {
        company_id: (bank_id, is_explicit or counts[company_id] == 1)
        for company_id, (bank_id, is_explicit) in fallbacks.items()
    }


def get_bank_entity_map(entity_codes):
    """`{codi_entitat: bank_id}` del catàleg, per traduir l'IBAN a `Bank`."""
    from coredata.models import Bank

    if not entity_codes:
        return {}

    return dict(
        Bank.objects.filter(token__in=entity_codes).values_list('token', 'id')
    )


def resolve_payment_banks(payments, manual_assignments=None, companies=None):
    """
    Decideix el compte de cada rebut i torna `(assignacions, avisos)`:

      - `assignacions`: `{id_pagament (str): id_company_bank (int)}`, amb només
        els rebuts que s'han pogut encaminar.
      - `avisos`: llista de `{code, count, payments}` per ensenyar a la pantalla
        de remeses. No bloquegen mai la generació.

    Precedència, de més concret a més general:
      0. assignació manual feta per l'usuari al llistat de rebuts,
      1. entitat del pagador (`payer_bank`),
      2. IBAN estranger (`foreign`),
      3. `default` de l'empresa, i si no n'hi ha, el seu compte per defecte.

    `companies` (ids de les empreses emissores seleccionades) només serveix per
    avisar dels rebuts que són d'una altra empresa: no els deixa fora, perquè
    qui tria les factures de la remesa és l'usuari.
    """
    manual_assignments = manual_assignments or {}
    selected_companies = {str(c) for c in companies} if companies else None

    rows = list(build_payments_values(payments))
    if not rows:
        return {}, []

    company_ids = {get_payment_company_id(row) for row in rows}
    company_ids.discard(None)

    routing_maps = get_company_routing_maps(company_ids)
    fallback_banks = get_company_fallback_banks(company_ids)

    parsed = {row['id']: parse_payer_iban(row['payment_bank']) for row in rows}
    entity_codes = {entity for _, entity in parsed.values() if entity}
    bank_by_entity = get_bank_entity_map(entity_codes)

    assignments = {}
    warnings = defaultdict(list)

    for row in rows:
        payment_id = str(row['id'])

        manual_bank = manual_assignments.get(payment_id, manual_assignments.get(row['id']))
        if manual_bank:
            assignments[payment_id] = int(manual_bank)
            continue

        company_id = get_payment_company_id(row)
        if not company_id and selected_companies and len(selected_companies) == 1:
            # Rebuts sense factura ni contracte (p. ex. devolucions a una
            # persona) no tenen d'on treure l'empresa. Si la remesa és d'una
            # sola empresa no hi ha cap ambigüitat i s'hi atribueixen, en lloc
            # de quedar-se fora sense que ningú se n'adoni.
            company_id = int(next(iter(selected_companies)))
        if not company_id:
            warnings['payment_without_company'].append(row['id'])
            continue

        if selected_companies is not None and str(company_id) not in selected_companies:
            warnings['payment_from_other_company'].append(row['id'])

        country, entity = parsed[row['id']]
        if not country:
            warnings['payment_without_iban'].append(row['id'])

        company_map = routing_maps[company_id]
        bank_id = None

        entity_bank_id = bank_by_entity.get(entity) if entity else None
        if entity_bank_id:
            bank_id = company_map['banks'].get(entity_bank_id)
        if not bank_id and country and country != 'ES':
            bank_id = company_map['foreign']
        if not bank_id:
            bank_id = company_map['default']
            if not bank_id:
                fallback_bank_id, is_explicit = fallback_banks.get(company_id, (None, False))
                bank_id = fallback_bank_id
                if bank_id and not is_explicit:
                    # L'empresa no té ni fila `default` al mapa ni cap compte
                    # marcat per defecte: el compte que s'hi acaba fent servir
                    # és el primer de la llista i no l'ha triat ningú.
                    warnings['company_without_default_bank'].append(row['id'])

        if not bank_id:
            warnings['company_without_bank'].append(row['id'])
            continue

        assignments[payment_id] = bank_id

    # Els avisos viatgen amb una mostra d'ids: el llistat sencer no cap a la
    # pantalla i el que interessa és el recompte.
    warning_list = [
        {'code': code, 'count': len(ids), 'payments': ids[:20]}
        for code, ids in warnings.items()
    ]

    return assignments, warning_list
