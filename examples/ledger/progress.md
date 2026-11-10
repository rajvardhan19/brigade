# Progress

## Piece 01: package skeleton and storage
- Status: done
- Files changed: ledger/__init__.py, ledger/__main__.py, ledger/db.py, ledger/importers.py (stub), ledger/rules.py (stub), ledger/budgets.py (stub), ledger/cli.py (stub), tests/test_db.py, .brigade/context.md
- Interface changes (also update context.md): none to signatures or columns. Additive only: CHECK constraint on `transactions.category_source` (NULL/'rule'/'manual') and an index on transactions(account, date); recorded in context.md.
- Notes for later pieces: connections return tuples (row_factory not set). Stubs carry their spec part as a module docstring. CLI stub raises NotImplementedError, so `python3 -m ledger` fails until piece 05.
- Check output (last lines):
  Ran 9 tests in 0.004s
  OK
  (import check of ledger.importers/rules/budgets/cli succeeded)

## Piece 02: CSV importers
- Status: done
- Files changed: ledger/importers.py, tests/test_importers.py, .brigade/context.md (Decisions)
- Interface changes (also update context.md): none
- Notes for later pieces: import_csv commits on success and rolls back on any error; ValueError messages are `line N: <reason>`; FileNotFoundError propagates (cli must catch OSError).
- Check output (last lines):
  Ran 22 tests in 0.013s
  OK

## Piece 03: categorization rules
- Status: done
- Files changed: ledger/rules.py, tests/test_rules.py, .brigade/context.md (Decisions)
- Interface changes (also update context.md): none
- Notes for later pieces: categorize commits once at the end; empty-string contains/pattern are stored as NULL. Spec and settled details did not conflict.
- Check output (last lines):
  Ran 40 tests in 0.019s
  OK

## Piece 04: budgets and monthly report
- Status: done
- Files changed: ledger/budgets.py, tests/test_budgets.py, .brigade/context.md (Decisions)
- Interface changes (also update context.md): none
- Notes for later pieces: set_budget/monthly_report raise ValueError on bad month or amount; amounts are cents (cli must convert dollars to int cents). Spec and settled details did not conflict.
- Check output (last lines):
  Ran 53 tests in 0.019s
  OK

## Piece 05: command line
- Status: done
- Files changed: ledger/cli.py, tests/test_cli.py, .brigade/context.md (Decisions)
- Interface changes (also update context.md): none
- Notes for later pieces: argparse writes usage errors to stderr itself (no `error:` prefix, exit 2); runtime errors print `error: <msg>` and exit 1. Earlier pieces' tests emit ResourceWarnings for unclosed sqlite connections (not from cli).
- Check output (last lines):
  Ran 67 tests in 0.125s
  OK
  `python3 -m ledger --db /nonexistent-dir/x.db report 2024-01` -> "error: unable to open database file", exit 1

## Review-fix (brigade defects 1-4)
Fixed huge/non-ASCII amount parsing in importers, strict dollar parsing in CLI `budget set`, 64-bit range checks in `add_rule`/`set_budget`, OverflowError backstop in `main`. Added tests in test_importers/test_cli/test_rules/test_budgets. 74 tests pass; all listed commands print `error: ...` with exit 1, no traceback.
