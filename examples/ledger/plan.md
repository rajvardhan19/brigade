# Plan: build the `ledger` personal-finance toolkit (stdlib Python)
Base commit: 96af3e9
Why split: the user asked for separate sessions. The job does split cleanly:
a schema/skeleton that fixes the contract, then three modules in separate
files, then the CLI on top.

## Waves
| Wave | Piece | Owns files | Model | Effort | Why this model |
|---|---|---|---|---|---|
| 1 | 01 skeleton + db (DONE) | ledger/__init__.py, ledger/db.py, ledger/__main__.py, stub ledger/{importers,rules,budgets,cli}.py, tests/test_db.py, .brigade/context.md | opus | medium | defines the schema and interfaces every later piece builds on |
| 2 | 02 importers (DONE) | ledger/importers.py, tests/test_importers.py | sonnet | medium | money parsing + atomic import; edge cases settled in prompt, tests catch errors, final opus review covers it |
| 2 | 03 rules (DONE) | ledger/rules.py, tests/test_rules.py | sonnet | medium | clear precedence rules, settled in prompt, testable |
| 2 | 04 budgets (DONE) | ledger/budgets.py, tests/test_budgets.py | sonnet | medium | simple aggregation, testable |
| 3 | 05 cli | ledger/cli.py, tests/test_cli.py | sonnet | medium | wires existing functions; output format and error paths checked by tests |
| 3 | review-final | (read only) | opus | medium | money handling; required after the last wave |

Wave 2 finished: 53 tests passing, no interface changes.

## How to run
- Start a piece with:
  claude --model <model> --effort <effort> "Do brigade piece NN: follow .brigade/prompts/NN-slug.md"
  In VS Code or the desktop app: open a new chat, pick the model, send the same sentence.
- Run the pieces in a wave one at a time. To run them in parallel instead,
  give each its own worktree (`claude --worktree NN-slug ...`) and merge
  them all before the next wave.
- **If a piece's check fails** and its session can't fix it: rerun the same
  prompt in a new session one model up (haiku -> sonnet -> opus), and paste
  the failure output under the prompt. Never retry on the same model twice.
  If opus fails, stop and run `/brigade:plan next` to re-plan.
- **Review:** after any wave that had a high-damage piece, and always after
  the last wave, run that wave's review prompt in a new session on opus. If
  it says DEFECTS, run its fix prompt once.
- When a wave is done, run `/brigade:plan next` for the next one.

## Spec (verbatim from the user; source of truth)
Build `ledger`, a small personal-finance toolkit, in this empty repository. Use only the Python 3 standard library (sqlite3, csv, decimal, argparse, re, ...). Put the package in `ledger/` and unittest tests in `tests/`, so that `python3 -m unittest discover -s tests` runs them.

Money is stored as integer cents everywhere: spending is negative, income is positive. Dates are stored as ISO strings (YYYY-MM-DD).

1. Storage: `ledger/db.py`
- `connect(path)` opens or creates a SQLite database, creates the schema if it doesn't exist, and returns a sqlite3.Connection. Connecting again to the same file keeps the existing data.
- `list_transactions(conn, account=None)` returns a list of dicts with the keys id, account, date, description, amount (cents) and category (None if uncategorized), ordered by date then id. With an account, only that account's transactions.

2. Importers: `ledger/importers.py`
- `import_csv(conn, path, bank, account)` imports a bank's CSV export into the named account and returns a tuple `(imported, skipped)`.
- Bank "acme": header `Date,Description,Amount`. Date is YYYY-MM-DD. Amount is a signed decimal, negative for spending, e.g. `-12.50`.
- Bank "zenith": header `Transaction Date,Payee,Debit,Credit`. Date is MM/DD/YYYY. Exactly one of Debit and Credit is filled in; Debit is spending (store it as negative). Amounts may have a leading `$` and thousands separators, e.g. `$1,234.56`.
- Descriptions are stored trimmed, with runs of whitespace inside them collapsed to a single space.
- A row is a duplicate if the same account already had a transaction with the same date, amount and description before this import started. Duplicates are skipped and counted in `skipped`. Rows within one file are never duplicates of each other. Importing the same file twice imports nothing the second time.
- An unknown bank raises ValueError. A row with a malformed date or amount (including a zenith row with neither or both of Debit and Credit) raises ValueError whose message includes `line N`, where N is the line number in the file (the header is line 1), and nothing from that file is imported.

3. Categorization rules: `ledger/rules.py`
- `add_rule(conn, category, contains=None, pattern=None, min_amount=None, max_amount=None, priority=0)` stores a rule and returns its id. A rule needs at least one of `contains` and `pattern`; otherwise raise ValueError.
- A rule matches a transaction when every condition it has holds: `contains` is a case-insensitive substring of the description; `pattern` is a case-insensitive regular expression found anywhere in the description (re.search); `min_amount` and `max_amount` are cents, compared inclusively with the absolute value of the amount.
- `categorize(conn, recategorize=False)` applies the rules and returns the number of transactions whose category changed. When several rules match, the highest priority wins; on a tie, the rule added first wins. By default only uncategorized transactions are touched; with `recategorize=True`, categories that rules assigned earlier are recomputed too. Transactions that no rule matches are left as they are.
- `set_category(conn, transaction_id, category)` sets a category by hand. Hand-set categories are never changed by `categorize`, even with `recategorize=True`.

4. Budgets and reports: `ledger/budgets.py`
- `set_budget(conn, category, month, amount)` sets a category's budget for a month in cents; month is "YYYY-MM". Setting it again replaces it.
- `monthly_report(conn, month)` returns a list of dicts with the keys category, spent, budget, remaining and over, for that month across all accounts. `spent` is the month's total spending in cents as a positive number (income is ignored). `budget` is None when no budget is set; `remaining` is budget minus spent, or None; `over` is True when spent is greater than budget. Uncategorized spending is reported under the category "Uncategorized". A category with a budget but no spending appears with spent 0. Rows are sorted by category name.

5. Command line: `ledger/cli.py`, also runnable as `python3 -m ledger`
- `main(argv)` takes the argument list and returns an exit code. Every command takes `--db PATH` before the subcommand.
- `import FILE --bank BANK --account NAME` prints `Imported N, skipped M`.
- `rule add CATEGORY [--contains TEXT] [--pattern REGEX] [--min CENTS] [--max CENTS] [--priority N]` prints `Rule N added`, where N is the new rule's id.
- `categorize [--all]` prints `Categorized N`; `--all` means recategorize.
- `budget set CATEGORY MONTH AMOUNT`, where AMOUNT is in dollars such as `250` or `250.00`, prints `Budget set`.
- `report MONTH` prints one line per report row: category, spent, budget and remaining, separated by tabs. Money is printed as dollars with two decimals (e.g. `123.45`, `-10.00`), None as `-`, and the word `OVER` is added as a fifth column when the row is over budget.
- Errors (a missing file, an unknown bank, a malformed CSV, bad arguments) print a message to stderr and return a non-zero exit code. They never print a traceback.

Add tests for each part.
