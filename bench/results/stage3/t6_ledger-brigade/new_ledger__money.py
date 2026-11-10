"""Helpers for converting between decimal strings and integer cents."""
from decimal import Decimal, InvalidOperation


def parse_cents(text):
    """Parse a decimal dollar string like '-12.50' or '$1,234.56' into cents.

    Raises ValueError on anything malformed or with sub-cent precision.
    """
    s = (text or "").strip()
    negative = False
    if s.startswith("-"):
        negative, s = True, s[1:].strip()
    if s.startswith("$"):
        s = s[1:].strip()
    if s.startswith("-") and not negative:
        negative, s = True, s[1:].strip()
    if "," in s:
        whole, _, frac = s.partition(".")
        groups = whole.split(",")
        if not groups[0] or len(groups[0]) > 3 or any(len(g) != 3 for g in groups[1:]):
            raise ValueError("bad thousands separators in %r" % text)
        s = "".join(groups) + ("." + frac if "." in s else "")
    if not s or not all(c.isdigit() or c == "." for c in s) or s.count(".") > 1 or s == ".":
        raise ValueError("invalid amount %r" % text)
    try:
        value = Decimal(s) * 100
    except InvalidOperation:
        raise ValueError("invalid amount %r" % text)
    if value != value.to_integral_value():
        raise ValueError("amount %r has more than two decimal places" % text)
    cents = int(value)
    return -cents if negative else cents


def format_cents(cents):
    if cents is None:
        return "-"
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return "%s%d.%02d" % (sign, cents // 100, cents % 100)
