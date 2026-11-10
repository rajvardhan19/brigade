"""Command-line interface for ledger."""
import argparse
import sqlite3
import sys

from ledger import budgets, db, importers, rules
from ledger.money import format_cents, parse_cents


class _ArgError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ArgError("%s: error: %s" % (self.prog, message))


def _build_parser():
    p = _Parser(prog="ledger", description="Personal-finance toolkit")
    p.add_argument("--db", required=True, metavar="PATH", help="database file")
    sub = p.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    sub.required = True

    imp = sub.add_parser("import", help="import a bank CSV export")
    imp.add_argument("file")
    imp.add_argument("--bank", required=True)
    imp.add_argument("--account", required=True)

    rule = sub.add_parser("rule", help="manage categorization rules")
    rsub = rule.add_subparsers(dest="rule_command", metavar="ACTION", parser_class=_Parser)
    rsub.required = True
    radd = rsub.add_parser("add", help="add a rule")
    radd.add_argument("category")
    radd.add_argument("--contains")
    radd.add_argument("--pattern")
    radd.add_argument("--min", type=int, metavar="CENTS")
    radd.add_argument("--max", type=int, metavar="CENTS")
    radd.add_argument("--priority", type=int, default=0)

    cat = sub.add_parser("categorize", help="apply rules")
    cat.add_argument("--all", action="store_true", help="recategorize rule-assigned too")

    bud = sub.add_parser("budget", help="manage budgets")
    bsub = bud.add_subparsers(dest="budget_command", metavar="ACTION", parser_class=_Parser)
    bsub.required = True
    bset = bsub.add_parser("set", help="set a monthly budget")
    bset.add_argument("category")
    bset.add_argument("month")
    bset.add_argument("amount", help="dollars, e.g. 250 or 250.00")

    rep = sub.add_parser("report", help="monthly budget report")
    rep.add_argument("month")
    return p


def _run(args):
    conn = db.connect(args.db)
    try:
        if args.command == "import":
            imported, skipped = importers.import_csv(conn, args.file, args.bank, args.account)
            print("Imported %d, skipped %d" % (imported, skipped))
        elif args.command == "rule":
            rid = rules.add_rule(conn, args.category, contains=args.contains,
                                 pattern=args.pattern, min_amount=args.min,
                                 max_amount=args.max, priority=args.priority)
            print("Rule %d added" % rid)
        elif args.command == "categorize":
            print("Categorized %d" % rules.categorize(conn, recategorize=args.all))
        elif args.command == "budget":
            amount = parse_cents(args.amount)
            if amount < 0:
                raise ValueError("budget amount must not be negative")
            budgets.set_budget(conn, args.category, args.month, amount)
            print("Budget set")
        elif args.command == "report":
            for row in budgets.monthly_report(conn, args.month):
                cols = [row["category"], format_cents(row["spent"]),
                        format_cents(row["budget"]), format_cents(row["remaining"])]
                if row["over"]:
                    cols.append("OVER")
                print("\t".join(cols))
    finally:
        conn.close()
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    try:
        args = _build_parser().parse_args(argv)
    except _ArgError as e:
        print(str(e), file=sys.stderr)
        return 2
    except SystemExit as e:  # --help
        return e.code if isinstance(e.code, int) else 0
    try:
        return _run(args)
    except (ValueError, OSError, sqlite3.Error) as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
