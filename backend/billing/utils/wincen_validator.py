"""
WinCen file validator and data extractor.

Usage:
    python wincen_validator.py <path_to_file.dat> [--csv output.csv]
"""
import sys
import csv
import argparse
from decimal import Decimal
from datetime import datetime

# ── Format definition ──────────────────────────────────────────────────────
FIELDS = [
    ('exploitation', 4,  'str'),
    ('contract',     8,  'str'),
    ('invoice',      14, 'str'),
    ('issue_date',   8,  'date'),
    ('reading_curr', 8,  'date'),
    ('reading_prev', 8,  'date'),
    ('prev_value',   9,  'int'),
    ('curr_value',   9,  'int'),
    ('consumption',  6,  'int'),
    ('subtotal',     64, 'cents'),
    ('total',        16, 'cents'),
]
LINE_WIDTH = sum(w for _, w, _ in FIELDS)  # 154


# ── Parsers ────────────────────────────────────────────────────────────────

def _parse_date(raw):
    raw = raw.strip()
    if not raw or set(raw) == {'0'}:
        return None
    try:
        return datetime.strptime(raw, '%Y%m%d').date().isoformat()
    except ValueError:
        return f'INVALID({raw})'


def _parse_int(raw):
    raw = raw.strip()
    if not raw or set(raw) == {'0'}:
        return 0
    try:
        return int(raw)
    except ValueError:
        return f'INVALID({raw})'


def _parse_cents(raw):
    raw = raw.strip()
    if not raw or set(raw) == {'0'}:
        return Decimal('0.00')
    try:
        return (Decimal(raw) / 100).quantize(Decimal('0.01'))
    except Exception:
        return f'INVALID({raw})'


def parse_line(line, line_num):
    errors = []
    actual = len(line)
    if actual != LINE_WIDTH:
        errors.append(f'Expected {LINE_WIDTH} chars, got {actual}')

    record = {'_line': line_num, '_errors': []}
    pos = 0
    for name, width, typ in FIELDS:
        chunk = line[pos:pos + width]
        if len(chunk) < width:
            errors.append(f'Field "{name}" truncated at pos {pos}')
            chunk = chunk.ljust(width)
        if typ == 'str':
            record[name] = chunk.strip()
        elif typ == 'date':
            record[name] = _parse_date(chunk)
        elif typ == 'int':
            record[name] = _parse_int(chunk)
        elif typ == 'cents':
            record[name] = _parse_cents(chunk)
        pos += width

    record['_errors'] = errors
    return record


# ── Main ───────────────────────────────────────────────────────────────────

def validate_and_extract(path):
    records = []
    global_errors = []

    with open(path, 'r', encoding='latin-1') as f:
        raw = f.read()

    lines = raw.splitlines()
    if not lines:
        print('ERROR: empty file')
        return [], []

    for i, line in enumerate(lines, start=1):
        if not line:
            continue
        record = parse_line(line, i)
        records.append(record)
        if record['_errors']:
            global_errors.append((i, record['_errors']))

    return records, global_errors


def print_summary(records, global_errors):
    total = len(records)
    invalid = len(global_errors)
    print(f'\n{"─"*60}')
    print(f'  Lines processed : {total}')
    print(f'  Lines with errors: {invalid}')
    if total:
        totals = [r['total'] for r in records if isinstance(r['total'], Decimal)]
        if totals:
            print(f'  Total amount sum : {sum(totals):,.2f}')
    print(f'{"─"*60}')

    if global_errors:
        print('\nERRORS:')
        for line_num, errs in global_errors[:20]:
            for e in errs:
                print(f'  Line {line_num:>5}: {e}')
        if len(global_errors) > 20:
            print(f'  … and {len(global_errors) - 20} more errors')

    if records:
        print('\nFirst 5 records:')
        for r in records[:5]:
            print(
                f"  L{r['_line']:>4} | expl={r['exploitation']} | "
                f"contract={r['contract']} | invoice={r['invoice']} | "
                f"date={r['issue_date']} | total={r['total']}"
            )


def write_csv(records, path):
    if not records:
        return
    fieldnames = [f for f, *_ in FIELDS]
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['_line'] + fieldnames + ['_errors'])
        writer.writeheader()
        for r in records:
            row = {k: v for k, v in r.items()}
            row['_errors'] = '; '.join(r['_errors'])
            writer.writerow(row)
    print(f'\nCSV saved to: {path}')


def main():
    parser = argparse.ArgumentParser(description='Validate and extract a WinCen .dat file')
    parser.add_argument('file', help='Path to the .dat file')
    parser.add_argument('--csv', metavar='OUTPUT', help='Export extracted data to CSV')
    args = parser.parse_args()

    records, global_errors = validate_and_extract(args.file)
    print_summary(records, global_errors)

    if args.csv:
        write_csv(records, args.csv)

    sys.exit(1 if global_errors else 0)


if __name__ == '__main__':
    main()
