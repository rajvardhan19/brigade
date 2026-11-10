"""Command line (spec part 5). Implemented by a later piece.

Also runnable as `python3 -m ledger`.
- main(argv) takes the argument list and returns an exit code. Every command
  takes `--db PATH` before the subcommand.
- `import FILE --bank BANK --account NAME` prints `Imported N, skipped M`.
- `rule add CATEGORY [--contains TEXT] [--pattern REGEX] [--min CENTS]
  [--max CENTS] [--priority N]` prints `Rule N added`, where N is the new
  rule's id.
- `categorize [--all]` prints `Categorized N`; `--all` means recategorize.
- `budget set CATEGORY MONTH AMOUNT`, where AMOUNT is in dollars such as `250`
  or `250.00`, prints `Budget set`.
- `report MONTH` prints one line per report row: category, spent, budget and
  remaining, separated by tabs. Money is printed as dollars with two decimals
  (e.g. `123.45`, `-10.00`), None as `-`, and the word `OVER` is added as a
  fifth column when the row is over budget.
- Errors (a missing file, an unknown bank, a malformed CSV, bad arguments)
  print a message to stderr and return a non-zero exit code. They never print
  a traceback.
"""


import argparse
import csv
import decimal
import re
import sqlite3
import sys

from ledger import budgets, db, importers, rules

_AMOUNT_RE = re.compile(r"\d+(\.\d+)?", re.ASCII)


def _fmt(cents):
    """Format integer cents as dollars with two decimals; None as `-`."""
    if cents is None:
        return "-"
    sign = "-" if cents < 0 else ""
    q, r = divmod(abs(cents), 100)
    return "%s%d.%02d" % (sign, q, r)


def _parse_amount(text):
    """Parse a dollar amount string into integer cents; raise ValueError."""
    text = text.strip()
    if not _AMOUNT_RE.fullmatch(text):
        raise ValueError("invalid amount %r" % text)
    d = decimal.Decimal(text)
    try:
        if d != d.quantize(decimal.Decimal("0.01")):
            raise ValueError("amount has more than 2 decimal places: %r" % text)
    except decimal.InvalidOperation:
        raise ValueError("amount out of range: %r" % text) from None
    cents = int(d * 100)
    if cents > 2**63 - 1:
        raise ValueError("amount out of range: %r" % text)
    return cents


def _build_parser():
    p = argparse.ArgumentParser(prog="ledger")
    p.add_argument("--db", required=True, metavar="PATH")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("import")
    s.add_argument("file")
    s.add_argument("--bank", required=True)
    s.add_argument("--account", required=True)

    rule = sub.add_parser("rule")
    rsub = rule.add_subparsers(dest="rule_command", required=True)
    s = rsub.add_parser("add")
    s.add_argument("category")
    s.add_argument("--contains")
    s.add_argument("--pattern")
    s.add_argument("--min", type=int)
    s.add_argument("--max", type=int)
    s.add_argument("--priority", type=int, default=0)

    s = sub.add_parser("categorize")
    s.add_argument("--all", action="store_true")

    bud = sub.add_parser("budget")
    bsub = bud.add_subparsers(dest="budget_command", required=True)
    s = bsub.add_parser("set")
    s.add_argument("category")
    s.add_argument("month")
    s.add_argument("amount")

    s = sub.add_parser("report")
    s.add_argument("month")
    return p


def _run(conn, args):
    cmd = args.command
    if cmd == "import":
        imported, skipped = importers.import_csv(
            conn, args.file, args.bank, args.account)
        print("Imported %d, skipped %d" % (imported, skipped))
    elif cmd == "rule":
        rid = rules.add_rule(
            conn, args.category, contains=args.contains,
            pattern=args.pattern, min_amount=args.min,
            max_amount=args.max, priority=args.priority)
        print("Rule %d added" % rid)
    elif cmd == "categorize":
        print("Categorized %d" % rules.categorize(conn, recategorize=args.all))
    elif cmd == "budget":
        cents = _parse_amount(args.amount)
        budgets.set_budget(conn, args.category, args.month, cents)
        print("Budget set")
    elif cmd == "report":
        for row in budgets.monthly_report(conn, args.month):
            cols = [row["category"], _fmt(row["spent"]),
                    _fmt(row["budget"]), _fmt(row["remaining"])]
            if row["over"]:
                cols.append("OVER")
            print("\t".join(cols))


def main(argv):
    """Run the CLI with `argv` (without the program name); return exit code."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    conn = None
    try:
        conn = db.connect(args.db)
        _run(conn, args)
    except (ValueError, OverflowError, OSError, csv.Error, sqlite3.Error) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()
    return 0
