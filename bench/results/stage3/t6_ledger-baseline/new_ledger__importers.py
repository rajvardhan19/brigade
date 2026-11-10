"""CSV importers for bank exports."""

import csv
import datetime
import re
from decimal import Decimal

_WS = re.compile(r"\s+")
_ACME_AMOUNT = re.compile(r"^[+-]?(\d+(\.\d{1,2})?|\.\d{1,2})$")
_ZENITH_AMOUNT = re.compile(
    r"^\$?(\d{1,3}(,\d{3})+|\d+)(\.\d{1,2})?$|^\$?\.\d{1,2}$"
)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_US_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def normalize_description(text):
    return _WS.sub(" ", text).strip()


def _to_cents(text):
    return int(Decimal(text) * 100)


def _parse_iso_date(text):
    text = text.strip()
    if not _ISO_DATE.match(text):
        raise ValueError(f"malformed date {text!r}")
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError(f"malformed date {text!r}") from None


def _parse_us_date(text):
    text = text.strip()
    if not _US_DATE.match(text):
        raise ValueError(f"malformed date {text!r}")
    try:
        return datetime.datetime.strptime(text, "%m/%d/%Y").date().isoformat()
    except ValueError:
        raise ValueError(f"malformed date {text!r}") from None


def _parse_acme_amount(text):
    text = text.strip()
    if not _ACME_AMOUNT.match(text):
        raise ValueError(f"malformed amount {text!r}")
    return _to_cents(text)


def _parse_zenith_amount(text):
    text = text.strip()
    if not _ZENITH_AMOUNT.match(text):
        raise ValueError(f"malformed amount {text!r}")
    return _to_cents(text.replace("$", "").replace(",", ""))


def _parse_acme(row):
    date_s, desc, amount_s = row
    return _parse_iso_date(date_s), desc, _parse_acme_amount(amount_s)


def _parse_zenith(row):
    date_s, desc, debit, credit = row
    debit, credit = debit.strip(), credit.strip()
    if bool(debit) == bool(credit):
        raise ValueError("exactly one of Debit and Credit must be filled in")
    date = _parse_us_date(date_s)
    if debit:
        amount = -_parse_zenith_amount(debit)
    else:
        amount = _parse_zenith_amount(credit)
    return date, desc, amount


BANKS = {
    "acme": (["Date", "Description", "Amount"], _parse_acme),
    "zenith": (["Transaction Date", "Payee", "Debit", "Credit"], _parse_zenith),
}


def _read_rows(path, bank):
    """Parse the whole file, returning [(date, description, cents), ...]."""
    header, parse = BANKS[bank]
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            first = next(reader, None)
            if first is None:
                raise ValueError("line 1: file is empty, expected header")
            if [c.strip() for c in first] != header:
                raise ValueError(
                    f"line 1: expected header {','.join(header)!r}, "
                    f"got {','.join(first)!r}"
                )
            while True:
                start = reader.line_num + 1
                try:
                    row = next(reader)
                except StopIteration:
                    break
                if not row or all(not c.strip() for c in row):
                    continue
                if len(row) != len(header):
                    raise ValueError(
                        f"line {start}: expected {len(header)} fields, got {len(row)}"
                    )
                try:
                    date, desc, amount = parse(row)
                except ValueError as e:
                    raise ValueError(f"line {start}: {e}") from None
                rows.append((date, normalize_description(desc), amount))
        except csv.Error as e:
            raise ValueError(f"line {reader.line_num}: {e}") from None
    return rows


def import_csv(conn, path, bank, account):
    """Import a bank CSV export into *account*; return (imported, skipped)."""
    if bank not in BANKS:
        raise ValueError(
            f"unknown bank {bank!r} (known: {', '.join(sorted(BANKS))})"
        )
    rows = _read_rows(path, bank)

    existing = {
        (r[0], r[1], r[2])
        for r in conn.execute(
            "SELECT date, amount, description FROM transactions WHERE account = ?",
            (account,),
        )
    }
    imported = skipped = 0
    with conn:
        for date, desc, amount in rows:
            if (date, amount, desc) in existing:
                skipped += 1
                continue
            conn.execute(
                "INSERT INTO transactions (account, date, description, amount)"
                " VALUES (?, ?, ?, ?)",
                (account, date, desc, amount),
            )
            imported += 1
    return imported, skipped
