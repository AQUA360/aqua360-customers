"""
Bulk planning of supply cuts: resolve a flat list of identifiers (strict
single type) to supply points, and detect conflicts with already-open cuts.

The resolver is deliberately separate from the view so the rules can be unit
tested without HTTP, mirroring `meter_lookup_service.py`.
"""
from django.db.models import Q

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


def build_preview(identifier_type, raw_identifiers, exclude_cut_id=None):
    """Full preview payload for the bulk-plan flow."""
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
    sp_ids = [sp.id for sp in supply_points]
    conflicts = detect_conflicts(sp_ids, exclude_cut_id=exclude_cut_id)
    conflict_ids = {c['supply_point_id'] for c in conflicts}

    resolved = []
    for sp in supply_points:
        brief = _supply_point_brief(sp, matched_by.get(sp.id, []))
        brief['has_conflict'] = sp.id in conflict_ids
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
        },
        'resolved': resolved,
        'not_found': not_found,
        'conflicts': conflicts,
    }
