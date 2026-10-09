from typing import Dict, List, Final, Optional

import schwifty


def get_spanish_bic(bank_code: str) -> Optional[str]:
    """
    Returns the official BIC for a Spanish bank code (e.g. "0081" or "81" -> "BSABESBB"),
    taken from the Banco de España registry bundled with schwifty, or None if unknown.
    The `Bank.bic` catalog only stores the 4-letter institution code ("BSAB"), which is
    not a valid BIC, so this is the source to trust.
    """
    if not bank_code or not str(bank_code).strip().isdigit():
        return None

    entries = schwifty.registry.get('bank_code').get(('ES', str(bank_code).strip().zfill(4))) or []
    if isinstance(entries, dict):
        entries = [entries]
    with_bic = [entry for entry in entries if entry.get('bic')]
    if not with_bic:
        return None
    primary = next((entry for entry in with_bic if entry.get('primary')), with_bic[0])
    return primary['bic']


def resolve_account_bic(iban: Optional[str], swift: Optional[str] = None,
                        catalog_bic: Optional[str] = None) -> Optional[str]:
    """
    Returns the 11-character BIC of an account, or None if it cannot be determined.
    Order: the account's own SWIFT, the `Bank.bic` catalog and, for Spanish IBANs, the
    official registry. Only complete values (8 or 11 characters) are trusted: a 4-letter
    institution code ("BSAB") is skipped instead of being padded by guesswork.
    """
    clean_iban: str = (iban or '').replace(' ', '').upper()
    candidates: List[Optional[str]] = [swift, catalog_bic]
    if clean_iban.startswith('ES'):
        candidates.append(get_spanish_bic(clean_iban[4:8]))

    for candidate in candidates:
        bic: str = (candidate or '').replace(' ', '').upper()
        if len(bic) == 11:
            return bic
        if len(bic) == 8:
            return f"{bic}XXX"
    return None


def get_spanish_bank_code_candidates(bank_code: str) -> List[str]:
    """
    Given the raw 4-digit Spanish bank code extracted from an IBAN (e.g. "0049"),
    returns the set of Bank.token values that should be considered equivalent:
    the zero-padded form and the leading-zeros-stripped form (e.g. "0049" and "49").
    Never matches an unrelated code (e.g. "1049") since only leading zeros are stripped/added.
    """
    if not bank_code or not bank_code.isdigit():
        return [bank_code] if bank_code else []

    stripped: str = str(int(bank_code))
    padded: str = bank_code.zfill(4)
    return list(dict.fromkeys([padded, stripped]))


def _calculate_spanish_digit(value_str: str, weights: List[int]) -> int:
    """
    Helper function to calculate a single Spanish control digit (0-9).
    Algorithm: 11 - (WeightedSum % 11). 
    Exceptions: If 11 -> 0, If 10 -> 1.
    """
    if len(value_str) != len(weights):
        raise ValueError("Value length and weights length must match")

    total_sum: int = 0
    i: int
    char: str
    
    
    for i, char in enumerate(value_str):
        digit: int = int(char)
        weight: int = weights[i]
        total_sum += digit * weight

    remainder: int = total_sum % 11
    result: int = 11 - remainder

    if result == 11:
        return 0
    if result == 10:
        return 1
    return result

def _validate_spanish_internal_structure(iban: str) -> bool:
    """
    Validates the internal 2 'Check Digits' (DC) of a Spanish IBAN.
    Format: ESxx bbbb ssss DC aaaaaaaaaa
    Indices: 0-3 (IBAN), 4-7 (Bank), 8-11 (Branch), 12-13 (DC), 14-23 (Account)
    """
    
    if len(iban) != 24:
        return False

    
    bank_code: str = iban[4:8]    # 4 digits
    branch_code: str = iban[8:12] # 4 digits 
    control_digits: str = iban[12:14] # 2 digits (Control)
    account_number: str = iban[14:24] # 10 digits

 
    # Weights for the first check digit (Bank + Branch)
    weights_group1: Final[List[int]] = [4, 8, 5, 10, 9, 7, 3, 6]
    
    # Weights for the second check digit (Account Number)
    weights_group2: Final[List[int]] = [1, 2, 4, 8, 5, 10, 9, 7, 3, 6]

    try:
        
        # Validate Bank + Branch
        calculated_digit1: int = _calculate_spanish_digit(
            bank_code + branch_code, 
            weights_group1
        )

        # Validate Account Number
        calculated_digit2: int = _calculate_spanish_digit(
            account_number, 
            weights_group2
        )

        expected_dc: str = f"{calculated_digit1}{calculated_digit2}"
        
        return control_digits == expected_dc

    except ValueError:
        return False


def validate_iban(iban: str) -> bool:
    # 1. Strict Typing and Sanitization
    sanitized_iban: str = iban.replace(" ", "").replace("-", "").upper()

    # 2. Country Configuration
    country_lengths: Dict[str, int] = {
        "DE": 22,  # Germany
        "FR": 27,  # France
        "ES": 24,  # Spain
        "GB": 22,  # United Kingdom
        "NL": 18,  # Netherlands
    }

    country_code: str = sanitized_iban[:2]

    # 3. Basic Validation Checks
    if country_code not in country_lengths:
        return False

    if len(sanitized_iban) != country_lengths[country_code]:
        return False

    # 4. Global Modulo 97 Check (The Mathematical Standard)
    # Move first 4 chars to the end: DE893704... -> 3704...DE89
    rearranged_iban: str = sanitized_iban[4:] + sanitized_iban[:4]

    numeric_iban_str: str = ""
    char: str
    
    for char in rearranged_iban:
        if char.isdigit():
            numeric_iban_str += char
        else:
            # Ord('A') is 65. So 65 - 55 = 10.
            val: int = ord(char) - 55
            numeric_iban_str += str(val)

    try:
        remainder: int = int(numeric_iban_str) % 97
    except ValueError:
        return False

    if remainder != 1:
        return False

    # 5. Specific Country Logic (Spain)
    # If the Global check passed, we now run the stricter local check
    if country_code == "ES":
        is_valid_spanish: bool = _validate_spanish_internal_structure(sanitized_iban)
        if not is_valid_spanish:
            return False

    return True