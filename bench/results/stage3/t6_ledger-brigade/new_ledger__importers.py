"""CSV importers for bank exports."""
import csv
import re
from datetime import datetime

from ledger.money import parse_cents

BANKS = {
    "acme": ["Date", "Description", "Amount"],
    "zenith": ["Transaction Date", "Payee", "Debit", "Credit"],
}


def normalize_description(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def _parse_date(text, fmt):
    return datetime.strptime((text or "").strip(), fmt).date().isoformat()


def _parse_acme(row):
    date = _parse_date(row["Date"], "%Y-%m-%d")
    return date, row["Description"], parse_cents(row["Amount"])


def _parse_zenith(row):
    date = _parse_date(row["Transaction Date"], "%m/%d/%Y")
    debit = (row["Debit"] or "").strip()
    credit = (row["Credit"] or "").strip()
    if bool(debit) == bool(credit):
        raise ValueError("exactly one of Debit and Credit must be filled in")
    if debit:
        amount = -abs(parse_cents(debit))
    else:
        amount = abs(parse_cents(credit))
    return date, row["Payee"], amount


PARSERS = {"acme": _parse_acme, "zenith": _parse_zenith}


def _read_rows(path, bank):
    expected = BANKS[bank]
    parse = PARSERS[bank]
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None or [h.strip() for h in header] != expected:
            raise ValueError("line 1: expected header %s" % ",".join(expected))
        for record in reader:
            line = reader.line_num
            if not any(cell.strip() for cell in record):
                continue  # blank line
            if len(record) != len(expected):
                raise ValueError("line %d: expected %d fields, got %d"
                                 % (line, len(expected), len(record)))
            try:
                date, desc, amount = parse(dict(zip(expected, record)))
            except ValueError as e:
                raise ValueError("line %d: %s" % (line, e)) from None
            rows.append((date, normalize_description(desc), amount))
    return rows


def import_csv(conn, path, bank, account):
    """Import a bank CSV into account. Returns (imported, skipped)."""
    if bank not in BANKS:
        raise ValueError("unknown bank %r (known: %s)" % (bank, ", ".join(sorted(BANKS))))
    rows = _read_rows(path, bank)  # validates everything before touching the db
    existing = {
        (r[0], r[1], r[2])
        for r in conn.execute(
            "SELECT date, amount, description FROM transactions WHERE account = ?",
            (account,))
    }
    imported = skipped = 0
    with conn:
        for date, desc, amount in rows:
            if (date, amount, desc) in existing:
                skipped += 1
                continue
            conn.execute(
                "INSERT INTO transactions (account, date, description, amount)"
                " VALUES (?, ?, ?, ?)", (account, date, desc, amount))
            imported += 1
    return imported, skipped
