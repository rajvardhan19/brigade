"""Command-line interface: python3 -m ledger --db PATH <command> ..."""

import argparse
import csv
import re
import sqlite3
import sys
from decimal import Decimal

from ledger import budgets, db, importers, rules

_DOLLARS = re.compile(r"^\$?(\d+(\.\d{1,2})?|\.\d{1,2})$")


class _ArgError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ArgError(f"{self.prog}: error: {message}")


def format_money(cents):
    if cents is None:
        return "-"
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def parse_dollars(text):
    text = text.strip()
    if not _DOLLARS.match(text):
        raise ValueError(f"malformed amount {text!r}, expected dollars like 250.00")
    return int(Decimal(text.lstrip("$")) * 100)


def build_parser():
    p = _Parser(prog="ledger", description="Personal-finance toolkit.")
    p.add_argument("--db", required=True, metavar="PATH", help="database file")
    sub = p.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    sub.required = True

    imp = sub.add_parser("import", help="import a bank CSV export")
    imp.add_argument("file")
    imp.add_argument("--bank", required=True)
    imp.add_argument("--account", required=True)

    rule = sub.add_parser("rule", help="manage categorization rules")
    rule_sub = rule.add_subparsers(dest="rule_command", metavar="ACTION",
                                   parser_class=_Parser)
    rule_sub.required = True
    add = rule_sub.add_parser("add", help="add a rule")
    add.add_argument("category")
    add.add_argument("--contains")
    add.add_argument("--pattern")
    add.add_argument("--min", type=int, dest="min_amount", metavar="CENTS")
    add.add_argument("--max", type=int, dest="max_amount", metavar="CENTS")
    add.add_argument("--priority", type=int, default=0)

    cat = sub.add_parser("categorize", help="apply rules to transactions")
    cat.add_argument("--all", action="store_true", help="recategorize too")

    budget = sub.add_parser("budget", help="manage budgets")
    budget_sub = budget.add_subparsers(dest="budget_command", metavar="ACTION",
                                       parser_class=_Parser)
    budget_sub.required = True
    bset = budget_sub.add_parser("set", help="set a monthly budget")
    bset.add_argument("category")
    bset.add_argument("month")
    bset.add_argument("amount")

    rep = sub.add_parser("report", help="monthly budget report")
    rep.add_argument("month")
    return p


def _run(args, out):
    conn = db.connect(args.db)
    try:
        if args.command == "import":
            imported, skipped = importers.import_csv(
                conn, args.file, args.bank, args.account)
            print(f"Imported {imported}, skipped {skipped}", file=out)
        elif args.command == "rule":
            rule_id = rules.add_rule(
                conn, args.category, contains=args.contains, pattern=args.pattern,
                min_amount=args.min_amount, max_amount=args.max_amount,
                priority=args.priority)
            print(f"Rule {rule_id} added", file=out)
        elif args.command == "categorize":
            n = rules.categorize(conn, recategorize=args.all)
            print(f"Categorized {n}", file=out)
        elif args.command == "budget":
            budgets.set_budget(conn, args.category, args.month,
                               parse_dollars(args.amount))
            print("Budget set", file=out)
        elif args.command == "report":
            for row in budgets.monthly_report(conn, args.month):
                cols = [row["category"], format_money(row["spent"]),
                        format_money(row["budget"]), format_money(row["remaining"])]
                if row["over"]:
                    cols.append("OVER")
                print("\t".join(cols), file=out)
    finally:
        conn.close()


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = build_parser().parse_args(argv)
    except _ArgError as e:
        print(e, file=sys.stderr)
        return 2
    except SystemExit as e:  # --help
        return e.code if isinstance(e.code, int) else 0
    try:
        _run(args, sys.stdout)
    except (ValueError, OSError, sqlite3.Error, csv.Error) as e:
        print(f"ledger: error: {e}", file=sys.stderr)
        return 1
    return 0
