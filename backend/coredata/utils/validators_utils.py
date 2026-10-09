import re

CONTROL_LETTERS = {
    "DNI": "TRWAGMYFPDXBNJZSQVHLCKE",
    "CIF": "JABCDEFGHI",
}

CIF_LAST_CHAR_TYPES = {
    "LETTER": lambda char: 'A' <= char <= 'Z',
    "NUMBER": lambda char: '0' <= char <= '9',
    "BOTH": lambda char: ('A' <= char <= 'Z') or ('0' <= char <= '9')
}


def validate_nif(nif):
    isDNI = False
    isNIE = False
    isCIF = False

    patternDNI = "[0-9]{8}[A-Z]"
    patternNIE = "[X-Z][0-9]{7}[A-Z]"
    patternCIF = "^[ABCDEFGHJKLMNPQRSUVW][0-9]{7}[A-Z0-9]$"

    size = len(nif)
    if size > 9:
        return False, ""

    validDNI = re.match(patternDNI, nif)
    validNIE = re.match(patternNIE, nif)
    validCIF = re.match(patternCIF, nif)

    isDNI = validDNI != None
    isNIE = validNIE != None
    isCIF = validCIF != None

    if isDNI:
        controlDigits = "TRWAGMYFPDXBNJZSQVHLCKE"
        none_valid = ['', '00000000T', 'X0000000T']

        if nif in none_valid:
            return False, ""

        numsDNI = int(nif[:8])
        lastControlDigit = nif[8]

        controlDigitValue = numsDNI % 23

        if lastControlDigit != controlDigits[controlDigitValue]:
            return False, ""

        return True, "DNI"

    elif isNIE:
        controlDigits = "TRWAGMYFPDXBNJZSQVHLCKE"
        numsNIE = int(nif[1:8])
        firstDigit = nif[0]
        lastControlDigit = nif[8]

        if firstDigit == 'X':
            controlDigitValue = numsNIE % 23
            if lastControlDigit != controlDigits[controlDigitValue]:
                return False, ""

        elif firstDigit == 'Y':
            controlDigitValue = (10000000 + numsNIE) % 23
            if lastControlDigit != controlDigits[controlDigitValue]:
                return False, ""

        elif firstDigit == 'Z':
            controlDigitValue = (20000000 + numsNIE) % 23
            if lastControlDigit != controlDigits[controlDigitValue]:
                return False, ""

        return True, "NIE"

    elif isCIF:
        first_char = nif[0]
        digits = nif[1:-1]
        last_char = nif[-1]

        if first_char in "PQSKW":
            last_char_type = "LETTER"
        elif first_char in "ABEH":
            last_char_type = "NUMBER"
        else:
            last_char_type = "BOTH"

        sum_even = sum(
            int(digits[i]) for i in range(1, len(digits), 2)
        )

        sum_odd = 0
        for i in range(0, len(digits), 2):
            doubled = int(digits[i]) * 2
            sum_odd += sum(int(x) for x in str(doubled))

        total_sum = sum_even + sum_odd

        control_index = (10 - (total_sum % 10)) % 10
        control_letter = CONTROL_LETTERS["CIF"][control_index]

        if not CIF_LAST_CHAR_TYPES[last_char_type](last_char):
            return False, ""

        if last_char.isdigit():
            if int(last_char) != control_index:
                return False, ""
        else:
            if last_char != control_letter:
                return False, ""

        return True, ""

    else:
        return False, ""


def is_valid_dni(value: str) -> bool:
    """
    Valida un DNI espanyol (8 dígits + lletra de control).
    Retorna True/False. No llença excepcions.
    """
    if not value:
        return False

    clean = str(value).strip().upper().replace(' ', '').replace('-', '')

    if len(clean) != 9:
        return False

    digits, letter = clean[:8], clean[8]

    if not digits.isdigit():
        return False

    expected_letter = CONTROL_LETTERS["DNI"][int(digits) % 23]
    return letter == expected_letter
