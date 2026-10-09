from coredata.models import ConfigProject

from billing.models import Invoice

# Installation-specific report: only invoices issued to a single recipient, whose NIF
# (Person.token) is configured per installation in this ConfigProject.
WINCEN_PERSON_TOKEN_CONFIG = 'wincen_person_token'

# Fixed prefixes used by the invoice numbering scheme (Factura/Factura rectificativa)
# that must not be part of the exported invoice number.
WINCEN_INVOICE_PREFIXES = ('FC', 'FF')


# ── Column widths ──────────────────────────────────────────────────────────
# Total per line: 4+10+14+8+8+8+9+9+6+64+16 = 156 chars, no separators, CRLF

_W = {
    'exploitation': 4,   # exploitation.token, right-justified
    'contract':    10,   # contract.token, right-justified
    'invoice':     14,   # serie_final/token, left-justified
    'date':         8,   # YYYYMMDD
    'reading':      9,   # integer, zero-padded
    'consumption':  6,   # integer, zero-padded
    'subtotal':    64,   # cents (×100), zero-padded
    'total':       16,   # cents (×100), zero-padded
}


# ── Helpers ────────────────────────────────────────────────────────────────

def _datestr(d):
    return d.strftime('%Y%m%d') if d else '0' * 8


def _zpad(value, width):
    try:
        return str(int(round(float(value or 0)))).zfill(width)
    except (TypeError, ValueError):
        return '0' * width


def _cents(value, width):
    try:
        cents = int(round(float(value or 0) * 100))
        return str(cents).zfill(width)
    except (TypeError, ValueError):
        return '0' * width


def _fixed_left(value, width):
    """Left-justify, truncate to exactly `width` chars."""
    return str(value or '').strip()[:width].ljust(width)


def _fixed_right(value, width):
    """Right-justify, truncate to exactly `width` chars."""
    return str(value or '').strip()[:width].rjust(width)


def _strip_invoice_prefix(value):
    for prefix in WINCEN_INVOICE_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


# ── Main generator ─────────────────────────────────────────────────────────

def generate_wincen_file(
    billing_id=None,
    include_readings=True,
    include_payments=True,
    progress_callback=None,
    start_date=None,
    end_date=None,
):
    """
    Generate a WinCen export file (.dat, fixed-width, no separators, CRLF).

    One line per invoice, 156 chars:
      [ 4] exploitation.token          right-justified
      [10] contract.token              right-justified
      [14] invoice serie_final/token   left-justified
      [ 8] issue_date                  YYYYMMDD
      [ 8] reading_date (current)      YYYYMMDD
      [ 8] reading_date (previous)     YYYYMMDD
      [ 9] prev reading value          integer zero-padded
      [ 9] curr reading value          integer zero-padded
      [ 6] consumption                 integer zero-padded
      [64] subtotal without VAT        cents (×100) zero-padded
      [16] total amount                cents (×100) zero-padded
    """
    # Informe específic d'una instal·lació: només factures emeses a un únic destinatari (per NIF).
    wincen_person_token = ConfigProject.objects.filter(token=WINCEN_PERSON_TOKEN_CONFIG).values_list('value', flat=True).first()
    if not wincen_person_token:
        raise ValueError(f"Cal configurar el ConfigProject '{WINCEN_PERSON_TOKEN_CONFIG}' amb el NIF del destinatari.")
    qs = Invoice.objects.filter(
        is_active=True,
        is_excluded=False,
        person__token=wincen_person_token,
    )

    # Només factures finals confirmades: exclou pressupostos i pre-factures.
    invoice_type_token = ConfigProject.objects.get(token='invoice_type_invoice_token').value
    pending_status_token = ConfigProject.objects.get(token='invoice_status_pending_token').value
    qs = qs.filter(type_final=invoice_type_token).exclude(status__token=pending_status_token)

    if billing_id:
        qs = qs.filter(billing_id=billing_id)
    elif start_date and end_date:
        qs = qs.filter(issue_date__range=(start_date, end_date))
    else:
        raise ValueError("Cal indicar billing_id o un rang de dates (start_date/end_date).")

    invoices = (
        qs
        .select_related(
            'contract',
            'exploitation',
        )
        .prefetch_related(
            'readings',
            'readings__previous_reading',
        )
        .order_by('contract__token', 'issue_date')
    )

    total = invoices.count()
    lines = []

    for i, invoice in enumerate(invoices):
        contract = invoice.contract

        # [4] exploitation token
        col1 = str(invoice.exploitation.token or '').strip()[:_W['exploitation']].zfill(_W['exploitation']) if invoice.exploitation else '0' * _W['exploitation']

        # [10] contract token
        col2 = str(contract.token or '').strip()[:_W['contract']].zfill(_W['contract']) if contract else '0' * _W['contract']

        # [14] invoice number — strip FC/FF prefix, remove slashes and spaces, zero-pad on the left
        raw_invoice = str(invoice.serie_final or invoice.token or '').replace('/', '').replace(' ', '')
        raw_invoice = _strip_invoice_prefix(raw_invoice)
        col3 = raw_invoice[:_W['invoice']].zfill(_W['invoice'])

        # [8] issue date
        col4 = _datestr(invoice.issue_date)

        # readings — first reading ordered by date
        readings = sorted(invoice.readings.all(), key=lambda r: r.reading_date or invoice.issue_date)
        reading = readings[0] if readings else None
        prev = reading.previous_reading if reading else None

        # [8] current reading date
        col5 = _datestr(reading.reading_date if reading else None)

        # [8] previous reading date
        col6 = _datestr(prev.reading_date if prev else None)

        # [9] previous reading value (integer)
        col7 = _zpad(prev.reading_value if prev else 0, _W['reading'])

        # [9] current reading value (integer)
        col8 = _zpad(reading.reading_value if reading else 0, _W['reading'])

        # [6] consumption (integer)
        col9 = _zpad(invoice.consumption or 0, _W['consumption'])

        # [64] subtotal without VAT in cents
        col10 = _cents(invoice.subtotal_final or 0, _W['subtotal'])

        # [16] total in cents
        col11 = _cents(invoice.total_final or 0, _W['total'])

        line = col1 + col2 + col3 + col4 + col5 + col6 + col7 + col8 + col9 + col10 + col11
        lines.append(line)

        if progress_callback and (i % 50 == 0 or i == total - 1):
            progress_callback(i + 1, total)

    return '\r\n'.join(lines) + '\r\n'
