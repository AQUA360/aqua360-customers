"""Resolve postal code / city for a Communication list/export row.

Most process-created communications only store `used_address` (a string snapshot)
and leave the `address` FK empty. Prefer the FK when present; otherwise recover
location from that snapshot.
"""
import re

from coredata.models import Address, City


def _single_postal_code_for_city(city):
    """Return the city's only linked postal code, or None if none/ambiguous."""
    if not city:
        return None
    codes = list(city.postal_codes.values_list('code', flat=True)[:2])
    return codes[0] if len(codes) == 1 else None


def _postal_code_from_text(used_address):
    match = re.search(r'\b(\d{5})\b', used_address or '')
    return match.group(1) if match else None


def _city_candidate_from_used_address(used_address):
    """Best-effort city name from Address.__str__ / invoice snapshot text."""
    text = (used_address or '').strip()
    if not text:
        return None

    # Non-ES Address.__str__: "line - postal - city - country" (parts may be omitted).
    if ' - ' in text:
        parts = [part.strip() for part in text.split(' - ') if part.strip()]
        if len(parts) >= 4:
            return parts[-2]
        if len(parts) == 3:
            # Could be line/postal/city or line/city/country; prefer non-numeric.
            for candidate in (parts[1], parts[2]):
                if candidate and not re.fullmatch(r'\d{5}', candidate):
                    return candidate
        if len(parts) == 2 and not re.fullmatch(r'\d{5}', parts[1]):
            return parts[1]

    # ES Address.__str__: "street line, City" (city is the last comma segment).
    segments = [segment.strip() for segment in text.split(',') if segment.strip()]
    if len(segments) >= 2:
        return segments[-1]
    return None


def resolve_communication_location(communication):
    """Return `(postal_code, city_name)` for a communication.

    1. Use `communication.address.address` when the FK is set (as stored).
    2. Otherwise match `used_address` to `Address.address_search`.
    3. Otherwise parse a city name from `used_address` and look it up;
       attach its single designated postal code when unambiguous.
    """
    cached = getattr(communication, '_resolved_location', None)
    if cached is not None:
        return cached

    person_address = getattr(communication, 'address', None)
    linked = getattr(person_address, 'address', None) if person_address else None
    if linked:
        city_name = None
        if linked.city_id and linked.city:
            city_name = linked.city.name
        elif linked.city_name:
            city_name = linked.city_name
        result = (linked.postal_code or None, city_name)
        communication._resolved_location = result
        return result

    used = (getattr(communication, 'used_address', None) or '').strip()
    if not used:
        result = (None, None)
        communication._resolved_location = result
        return result

    matched = (
        Address.objects.filter(address_search=used)
        .select_related('city')
        .prefetch_related('city__postal_codes')
        .first()
    )
    if matched:
        city_name = None
        if matched.city_id and matched.city:
            city_name = matched.city.name
        elif matched.city_name:
            city_name = matched.city_name
        postal = matched.postal_code or None
        if not postal and matched.city_id:
            postal = _single_postal_code_for_city(matched.city)
        result = (postal, city_name)
        communication._resolved_location = result
        return result

    postal_in_text = _postal_code_from_text(used)
    city_candidate = _city_candidate_from_used_address(used)
    if not city_candidate:
        result = (postal_in_text, None)
        communication._resolved_location = result
        return result

    city = City.objects.filter(name__iexact=city_candidate).prefetch_related('postal_codes').first()
    if not city:
        result = (postal_in_text, None)
        communication._resolved_location = result
        return result

    postal = postal_in_text or _single_postal_code_for_city(city)
    result = (postal, city.name)
    communication._resolved_location = result
    return result
