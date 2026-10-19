"""
Bulk planning of supply cuts: resolve a flat list of identifiers (strict
single type) to supply points, and detect conflicts with already-open cuts.

The resolver is deliberately separate from the view so the rules can be unit
tested without HTTP, mirroring `meter_lookup_service.py`.
"""
from django.db.models import Q

from contract.models import Contract
from coredata.models import Street

from ..models import SupplyCut, SupplyPoint
from . import supply_cut_service


MAX_IDENTIFIERS = 5000

IDENTIFIER_CONTRACT_TOKEN = 'contract_token'
IDENTIFIER_SUPPLY_POINT_ID = 'supply_point_id'
IDENTIFIER_STREET_ID = 'street_id'
IDENTIFIER_TYPES = (
    IDENTIFIER_CONTRACT_TOKEN,
    IDENTIFIER_SUPPLY_POINT_ID,
    IDENTIFIER_STREET_ID,
)


class BulkPlanError(Exception):
    """A user-facing validation error (mapped to HTTP 400 by the view)."""

    def __init__(self, message, code='invalid'):
        super().__init__(message)
        self.message = message
        self.code = code


def normalize_identifiers(identifier_type, raw_identifiers):
    """Strip, drop empties and dedupe preserving first-seen order.

    `supply_point_id` and `street_id` are integer keys: a non-numeric line is
    kept verbatim so it surfaces in `not_found` instead of crashing the
    request. Names are never accepted — street names collide in ~30% of rows.
    """
    if not isinstance(raw_identifiers, (list, tuple)):
        raise BulkPlanError("El camp 'identifiers' ha de ser una llista.", code='not_a_list')

    seen = set()
    result = []
    for raw in raw_identifiers:
        value = str(raw).strip() if raw is not None else ''
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _integer_keys(values):
    """Split normalized values into (ints, non_integers).

    A value is an integer key when every character is a digit (after the
    strip already done by `normalize_identifiers`).
    """
    ints, non_integers = [], []
    for value in values:
        if value.isdigit():
            ints.append(int(value))
        else:
            non_integers.append(value)
    return ints, non_integers


def _supply_point_brief(supply_point, matched_by):
    address = supply_point.address
    street = address.street if address else None
    return {
        'supply_point_id': supply_point.id,
        'token': supply_point.token or '',
        'address': str(address) if address else '',
        'street_id': street.id if street else None,
        'street_label': str(street) if street else '',
        'matched_by': matched_by,
    }


def _resolve_contract_tokens(tokens):
    supply_points = (
        SupplyPoint.objects
        .filter(Q(contracts__token__in=tokens) | Q(default_contracts__token__in=tokens))
        .select_related('address__street')
        .distinct()
    )
    # Which contract token matched each point (for the preview's sanity column),
    # in ONE query instead of one per token.
    rows = (
        SupplyPoint.objects
        .filter(Q(contracts__token__in=tokens) | Q(default_contracts__token__in=tokens))
        .values_list('id', 'contracts__token', 'default_contracts__token')
        .distinct()
    )
    by_token = {}
    for sp_id, contract_token, default_token in rows:
        for token in (contract_token, default_token):
            if token:
                matched = by_token.setdefault(sp_id, [])
                if token not in matched:
                    matched.append(token)
    return supply_points, by_token


def _resolve_supply_point_ids(ids):
    return (
        SupplyPoint.objects
        .filter(id__in=ids)
        .select_related('address__street')
    )


def _resolve_contract_ids(contract_ids):
    if not contract_ids:
        return SupplyPoint.objects.none()
    return (
        SupplyPoint.objects
        .filter(Q(contracts__id__in=contract_ids) | Q(default_contracts__id__in=contract_ids))
        .select_related('address__street')
        .distinct()
    )


def _parse_manual_ids(values):
    """Tolerant parse of a manual id array: non-lists -> ([], []).

    Returns `(int_ids, unparsable_labels)` so garbage entries can be
    surfaced in `not_found` instead of vanishing silently.
    """
    if not isinstance(values, (list, tuple)):
        return [], []
    int_ids = []
    unparsable = []
    for value in values:
        if isinstance(value, bool):
            continue
        try:
            int_ids.append(int(value))
        except (TypeError, ValueError):
            label = str(value).strip() if value is not None else ''
            if label:
                unparsable.append(label)
    return int_ids, unparsable


def _merge_manual_points(supply_points, manual_supply_point_ids, manual_contract_ids):
    """Append picker-selected points/contracts to the resolved text list.

    Dedupes by id (text-resolved rows win, keeping their `matched_by`);
    requested manual ids that do not resolve are reported so the caller can
    surface them in `not_found` instead of dropping them silently. Misses
    are tracked per domain: unresolved supply-point ids stay numeric (the
    native idiom of that identifier mode), unresolved contracts are labelled
    with their commercial token (raw id only when the contract does not
    exist). Returns `(merged_supply_points, manual_not_found)`.
    """
    manual_ids, manual_unparsable = _parse_manual_ids(manual_supply_point_ids)
    contract_ids, contract_unparsable = _parse_manual_ids(manual_contract_ids)

    seen = set()
    merged = []
    for sp in supply_points:
        if sp.id not in seen:
            seen.add(sp.id)
            merged.append(sp)

    manual_points = list(_resolve_supply_point_ids(manual_ids))
    found_sp_ids = {sp.id for sp in manual_points}
    contract_points = list(_resolve_contract_ids(contract_ids))
    linked_contracts = set()
    if contract_ids:
        linked_contracts = set(
            Contract.objects.filter(
                Q(id__in=contract_ids),
                Q(supply_points__isnull=False) | Q(supply_point_default__isnull=False),
            ).values_list('id', flat=True)
        )
    for sp in manual_points + contract_points:
        if sp.id not in seen:
            seen.add(sp.id)
            merged.append(sp)

    manual_not_found = [
        str(value) for value in dict.fromkeys(manual_ids) if value not in found_sp_ids
    ]
    if contract_ids:
        tokens = dict(
            Contract.objects.filter(id__in=contract_ids).values_list('id', 'token')
        )
        for value in dict.fromkeys(contract_ids):
            if value in linked_contracts:
                continue
            token = str(tokens.get(value) or '').strip()
            manual_not_found.append(token if token else str(value))
    manual_not_found += list(dict.fromkeys(manual_unparsable + contract_unparsable))
    return merged, manual_not_found


def _resolve_street_ids(ids):
    # A street resolves to every supply point located on it. `is_active=True`
    # keeps decommissioned points out: planning a cut onto them is meaningless.
    return (
        SupplyPoint.objects
        .filter(address__street__id__in=ids, is_active=True)
        .select_related('address__street')
        .distinct()
    )


def resolve_identifiers(identifier_type, identifiers):
    """Resolve a normalized identifier list to supply points.

    Returns `(supply_points, not_found, matched_by)`.
    """
    if identifier_type == IDENTIFIER_CONTRACT_TOKEN:
        supply_points, by_token = _resolve_contract_tokens(identifiers)
        matched_by = {sp_id: tokens for sp_id, tokens in by_token.items()}
        matched_tokens = set()
        for tokens in by_token.values():
            matched_tokens.update(tokens)
        not_found = [t for t in identifiers if t not in matched_tokens]
        return list(supply_points), not_found, matched_by

    if identifier_type == IDENTIFIER_SUPPLY_POINT_ID:
        ints, non_integers = _integer_keys(identifiers)
        supply_points = list(_resolve_supply_point_ids(ints))
        found_ids = {sp.id for sp in supply_points}
        not_found = non_integers + [str(i) for i in ints if i not in found_ids]
        return supply_points, not_found, {}

    if identifier_type == IDENTIFIER_STREET_ID:
        ints, non_integers = _integer_keys(identifiers)
        supply_points = list(_resolve_street_ids(ints))
        # A street with no addresses resolves to zero points: the street id is
        # still valid, so it must NOT be reported as not_found — only an
        # unknown id or a non-numeric line is.
        matched_street_ids = set(
            Street.objects.filter(id__in=ints).values_list('id', flat=True)
        )
        not_found = non_integers + [str(i) for i in ints if i not in matched_street_ids]
        return supply_points, not_found, {}

    raise BulkPlanError(
        "Tipus d'identificador desconegut: {}.".format(identifier_type),
        code='unknown_type',
    )


def detect_conflicts(supply_point_ids, exclude_cut_id=None):
    """Other non-closed cuts already linked to those supply points.

    "Open" means the cut still has an effect or is planned to have one:
    `is_active=True` and a status outside the closed family {Acabat, Cancel·lat}.
    This covers both PLANNED and ACTIVE cuts and skips the Conflicte
    quarantine only through its status, never through `requires_review`.
    """
    if not supply_point_ids:
        return []

    closed_tokens = supply_cut_service.closed_status_tokens()
    cuts = (
        SupplyCut.objects
        .filter(supply_points__id__in=supply_point_ids, is_active=True)
        .exclude(status__token__in=closed_tokens)
        .select_related('status', 'cause')
        .distinct()
    )
    if exclude_cut_id:
        cuts = cuts.exclude(id=exclude_cut_id)

    cuts_by_sp = {sp_id: [] for sp_id in supply_point_ids}
    sp_ids_in_cut = {}
    for cut in cuts:
        ids = list(cut.supply_points.filter(id__in=supply_point_ids).values_list('id', flat=True))
        for sp_id in ids:
            cuts_by_sp.setdefault(sp_id, []).append(cut)
        sp_ids_in_cut[cut.id] = ids

    conflicts = []
    for sp_id, sp_cuts in cuts_by_sp.items():
        if not sp_cuts:
            continue
        conflicts.append({
            'supply_point_id': sp_id,
            'cuts': [
                {
                    'id': cut.id,
                    'token': cut.token or '',
                    'status': cut.status.name if cut.status else '',
                    'status_color': getattr(cut.status, 'color', None),
                    'date_start': cut.date_start.isoformat() if cut.date_start else None,
                    'date_end': cut.date_end.isoformat() if cut.date_end else None,
                }
                for cut in sp_cuts
            ],
        })
    return conflicts


def detect_vulnerable(supply_point_ids):
    """Supply points whose active contracts link to a vulnerable person.

    A person is vulnerable when `Person.vulnerability_level != 0` (currently
    1 = En Risc and 2 = Vulnerable; any future non-zero state is covered too).
    The roles checked are the holder, tenant and owner of every ACTIVE
    contract linked to the point, through both the M2M `supply_points` and
    the `supply_point_default` FK.

    Two queries total regardless of how many supply points are passed — one
    per relation direction, each joining the three person roles via
    `values_list`, so no N+1. Result shaped like `detect_conflicts`, one
    entry per affected supply point:

        [{'supply_point_id': id,
          'people': [{'person_id': id, 'role': 'holder'|'tenant'|'owner',
                      'vulnerability_level': int}, ...]}, ...]
    """
    if not supply_point_ids:
        return []

    roles = ('holder', 'tenant', 'owner')
    person_columns = tuple(
        column
        for role in roles
        for column in ('{}_id'.format(role), '{}__vulnerability_level'.format(role))
    )
    m2m_rows = (
        Contract.objects
        .filter(supply_points__id__in=supply_point_ids, is_active=True)
        .values_list('supply_points__id', *person_columns)
    )
    default_rows = (
        Contract.objects
        .filter(supply_point_default_id__in=supply_point_ids, is_active=True)
        .values_list('supply_point_default_id', *person_columns)
    )

    # sp_id -> {(person_id, role): level}; the tuple key dedupes the same
    # person/role appearing through several contracts on the same point.
    vulnerable_by_sp = {}
    for rows in (m2m_rows, default_rows):
        for row in rows:
            sp_id = row[0]
            for role_index, role in enumerate(roles):
                person_id = row[1 + role_index * 2]
                level = row[2 + role_index * 2]
                if person_id is None or not level:
                    continue
                per_sp = vulnerable_by_sp.setdefault(sp_id, {})
                per_sp.setdefault((person_id, role), level)

    return [
        {
            'supply_point_id': sp_id,
            'people': [
                {
                    'person_id': person_id,
                    'role': role,
                    'vulnerability_level': level,
                }
                for (person_id, role), level in per_sp.items()
            ],
        }
        for sp_id, per_sp in vulnerable_by_sp.items()
    ]


def build_preview(
    identifier_type,
    raw_identifiers,
    exclude_cut_id=None,
    manual_supply_point_ids=None,
    manual_contract_ids=None,
):
    """Full preview payload for the bulk-plan flow.

    Combines the pasted identifier list with any picker-selected manual
    supply points/contracts in the same payload: the merge is deduped by id
    and conflicts/vulnerability run over the combined set, so no manually
    added point can slip past validation or be left out of the final save.
    """
    if identifier_type not in IDENTIFIER_TYPES:
        raise BulkPlanError(
            "Tipus d'identificador desconegut: {}.".format(identifier_type),
            code='unknown_type',
        )

    identifiers = normalize_identifiers(identifier_type, raw_identifiers)
    if len(identifiers) > MAX_IDENTIFIERS:
        raise BulkPlanError(
            "Com a màxim {} identificadors (s'han rebut {}).".format(
                MAX_IDENTIFIERS, len(identifiers)
            ),
            code='over_cap',
        )

    supply_points, not_found, matched_by = resolve_identifiers(identifier_type, identifiers)
    text_ids = {sp.id for sp in supply_points}
    supply_points, manual_not_found = _merge_manual_points(
        supply_points, manual_supply_point_ids, manual_contract_ids,
    )
    not_found = list(not_found) + manual_not_found
    sp_ids = [sp.id for sp in supply_points]
    conflicts = detect_conflicts(sp_ids, exclude_cut_id=exclude_cut_id)
    conflict_ids = {c['supply_point_id'] for c in conflicts}
    vulnerable = detect_vulnerable(sp_ids)
    vulnerable_ids = {v['supply_point_id'] for v in vulnerable}

    resolved = []
    for sp in supply_points:
        if sp.id in text_ids:
            brief = _supply_point_brief(sp, matched_by.get(sp.id, []))
        else:
            brief = _supply_point_brief(sp, ['manual'])
        brief['has_conflict'] = sp.id in conflict_ids
        brief['has_vulnerable_person'] = sp.id in vulnerable_ids
        resolved.append(brief)

    return {
        'identifier_type': identifier_type,
        'stats': {
            'total_input': len(raw_identifiers) if isinstance(raw_identifiers, (list, tuple)) else 0,
            'unique': len(identifiers),
            'duplicates_in_input': (
                (len(raw_identifiers) if isinstance(raw_identifiers, (list, tuple)) else 0)
                - len(identifiers)
            ),
            'resolved': len(resolved),
            'not_found': len(not_found),
            'conflicts': len(conflicts),
            'vulnerable': len(vulnerable),
        },
        'resolved': resolved,
        'not_found': not_found,
        'conflicts': conflicts,
        'vulnerable': vulnerable,
    }
