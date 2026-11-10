"""CSV importers (spec part 2). Implemented by a later piece.

- import_csv(conn, path, bank, account) imports a bank's CSV export into the
  named account and returns a tuple (imported, skipped).
- Bank "acme": header `Date,Description,Amount`. Date is YYYY-MM-DD. Amount is
  a signed decimal, negative for spending, e.g. `-12.50`.
- Bank "zenith": header `Transaction Date,Payee,Debit,Credit`. Date is
  MM/DD/YYYY. Exactly one of Debit and Credit is filled in; Debit is spending
  (store it as negative). Amounts may have a leading `$` and thousands
  separators, e.g. `$1,234.56`.
- Descriptions are stored trimmed, with runs of whitespace inside them
  collapsed to a single space.
- A row is a duplicate if the same account already had a transaction with the
  same date, amount and description before this import started. Duplicates
  are skipped and counted in `skipped`. Rows within one file are never
  duplicates of each other. Importing the same file twice imports nothing the
  second time.
- An unknown bank raises ValueError. A row with a malformed date or amount
  (including a zenith row with neither or both of Debit and Credit) raises
  ValueError whose message includes `line N`, where N is the line number in
  the file (the header is line 1), and nothing from that file is imported.
"""

import csv
import datetime
import decimal
import re
from decimal import Decimal

_MAX_CENTS = 2**63 - 1

_ACME_AMOUNT = re.compile(r"^[+-]?\d+(\.\d{1,2})?$", re.ASCII)
_ZENITH_AMOUNT = re.compile(
    r"^\$?\d{1,3}(,\d{3})*(\.\d{1,2})?$|^\$?\d+(\.\d{1,2})?$", re.ASCII)
_ACME_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$", re.ASCII)
_ZENITH_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$", re.ASCII)

_HEADERS = {
    "acme": ["Date", "Description", "Amount"],
    "zenith": ["Transaction Date", "Payee", "Debit", "Credit"],
}


def _parse_date(text, regex, fmt):
    text = text.strip()
    if not regex.match(text):
        raise ValueError("malformed date %r" % text)
    try:
        return datetime.datetime.strptime(text, fmt).strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError("malformed date %r" % text) from None


def _to_cents(text, regex):
    text = text.strip()
    if not regex.match(text):
        raise ValueError("malformed amount %r" % text)
    d = Decimal(text.replace("$", "").replace(",", ""))
    try:
        if d != d.quantize(Decimal("0.01")):
            raise ValueError("malformed amount %r" % text)
    except decimal.InvalidOperation:
        raise ValueError("malformed amount %r" % text) from None
    cents = int(d * 100)
    if abs(cents) > _MAX_CENTS:
        raise ValueError("malformed amount %r (out of range)" % text)
    return cents


def _parse_acme(row):
    date = _parse_date(row[0], _ACME_DATE, "%Y-%m-%d")
    return date, row[1], _to_cents(row[2], _ACME_AMOUNT)


def _parse_zenith(row):
    date = _parse_date(row[0], _ZENITH_DATE, "%m/%d/%Y")
    debit, credit = row[2].strip(), row[3].strip()
    if bool(debit) == bool(credit):
        raise ValueError("exactly one of Debit and Credit must be filled in")
    if debit:
        amount = -_to_cents(debit, _ZENITH_AMOUNT)
    else:
        amount = _to_cents(credit, _ZENITH_AMOUNT)
    return date, row[1], amount


_PARSERS = {"acme": _parse_acme, "zenith": _parse_zenith}


def import_csv(conn, path, bank, account):
    """Import a bank CSV into `account`; return (imported, skipped)."""
    if bank not in _HEADERS:
        raise ValueError("unknown bank %r" % (bank,))
    header = _HEADERS[bank]
    parse = _PARSERS[bank]

    parsed = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        first = next(reader, None)
        if first is None:
            raise ValueError("line 1: empty file, expected header")
        if [c.strip() for c in first] != header:
            raise ValueError("line 1: header must be %s" % ",".join(header))
        for row in reader:
            if not any(c.strip() for c in row):
                continue
            n = reader.line_num
            if len(row) != len(header):
                raise ValueError(
                    "line %d: expected %d columns, got %d"
                    % (n, len(header), len(row)))
            try:
                date, desc, amount = parse(row)
            except ValueError as e:
                raise ValueError("line %d: %s" % (n, e)) from None
            parsed.append((date, " ".join(desc.split()), amount))

    try:
        existing = set(conn.execute(
            "SELECT date, amount, description FROM transactions"
            " WHERE account = ?", (account,)))
        imported = skipped = 0
        for date, desc, amount in parsed:
            if (date, amount, desc) in existing:
                skipped += 1
                continue
            conn.execute(
                "INSERT INTO transactions"
                " (account, date, description, amount, category,"
                " category_source) VALUES (?, ?, ?, ?, NULL, NULL)",
                (account, date, desc, amount))
            imported += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return imported, skipped
