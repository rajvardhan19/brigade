# Project context
`ledger`: a small personal-finance toolkit in pure Python 3 standard library
(sqlite3, csv, decimal, argparse, re). Greenfield: this job builds storage,
CSV importers, categorization rules, budgets/reports and a CLI. The full
original spec is in `.brigade/plan.md` under "Spec"; it is the source of truth.

## Layout
- `ledger/__init__.py` - package marker
- `ledger/db.py` - connect(), schema, list_transactions()
- `ledger/importers.py` - import_csv()
- `ledger/rules.py` - add_rule(), categorize(), set_category()
- `ledger/budgets.py` - set_budget(), monthly_report()
- `ledger/cli.py` - main(argv)
- `ledger/__main__.py` - `raise SystemExit(main(sys.argv[1:]))`
- `tests/test_<module>.py` - one unittest file per module (`tests/__init__.py` absent; discover with -s tests)

## Commands
- Test: `python3 -m unittest discover -s tests`
- Run CLI: `python3 -m ledger --db PATH <subcommand> ...`

## Conventions
- Standard library only. No third-party packages.
- Money is integer cents everywhere (spending negative, income positive).
  Parse decimals with `decimal.Decimal`, never float.
- Dates stored as ISO `YYYY-MM-DD` strings.
- Library functions take a `sqlite3.Connection` as first arg, commit their own
  writes, and raise `ValueError` for bad input. Only cli.py prints.
- Tests use `connect(":memory:")` or a file in `tempfile.TemporaryDirectory()`.
  Tests may build fixtures by inserting via public functions or raw SQL on the
  schema below.

## Interfaces between parts
(Confirmed by piece 01; matches ledger/db.py. Later pieces rely on it.)

Schema (created by `db.connect`, `CREATE TABLE IF NOT EXISTS`):
- `transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT NOT NULL,
  date TEXT NOT NULL, description TEXT NOT NULL, amount INTEGER NOT NULL,
  category TEXT NULL, category_source TEXT NULL)`
  `category_source` is NULL (uncategorized), `'rule'` or `'manual'`
  (enforced by a CHECK constraint). Index `transactions_account_date` on
  (account, date) for duplicate lookups.
- `rules(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
  contains TEXT NULL, pattern TEXT NULL, min_amount INTEGER NULL,
  max_amount INTEGER NULL, priority INTEGER NOT NULL DEFAULT 0)`
  "Added first" = lower id.
- `budgets(category TEXT NOT NULL, month TEXT NOT NULL, amount INTEGER NOT NULL,
  PRIMARY KEY(category, month))`

Functions:
- `db.connect(path) -> sqlite3.Connection`
- `db.list_transactions(conn, account=None) -> list[dict]` keys id, account,
  date, description, amount, category; ordered by date, id.
- `importers.import_csv(conn, path, bank, account) -> (imported, skipped)`
- `rules.add_rule(conn, category, contains=None, pattern=None, min_amount=None, max_amount=None, priority=0) -> int`
- `rules.categorize(conn, recategorize=False) -> int`
- `rules.set_category(conn, transaction_id, category) -> None`
- `budgets.set_budget(conn, category, month, amount) -> None`
- `budgets.monthly_report(conn, month) -> list[dict]` keys category, spent,
  budget, remaining, over
- `cli.main(argv) -> int`

## Decisions
- Split into sessions on user request.
- Piece 01: `db.connect` does NOT set `conn.row_factory`; rows from
  `conn.execute` are tuples. Set a row_factory on your own cursor if wanted.
- Piece 01: `db.connect` runs the schema via `executescript` and commits; it
  does not enable foreign keys or change isolation_level (default), so
  callers needing atomicity (importer) can rely on normal implicit
  transactions + `conn.commit()` / `conn.rollback()`.
- Piece 01: `list_transactions` never exposes `category_source`; modules that
  need it (rules) query the table directly.
- Piece 01: `ledger/__main__.py` imports `ledger.cli.main` at module level.
- Piece 02: importer regexes also require strict date shapes (`YYYY-MM-DD`, `MM/DD/YYYY`, zero-padded) and acme amounts allow an optional `+`/`-` with 1-2 decimals (so `1.230` is malformed). Rows whose cells are all blank are skipped.
- Piece 03: an empty-string `contains`/`pattern` counts as absent (stored as NULL). `categorize` counts a NULL-source row as changed even if the category text is the same (it gains source 'rule'). `set_category` rolls back and raises ValueError on unknown id.
- Piece 04: month is validated with `fullmatch` (ASCII digits, so no trailing newline); non-str month raises ValueError. `monthly_report` returns rows with `over` as a real bool and money as ints.
- Piece 05: `budget set` rejects amounts whose value is not exactly representable in cents (so `250.000` is accepted as 25000, `250.001` rejected); `decimal.InvalidOperation` is converted to ValueError. `main` returns `e.code` from argparse's SystemExit (2 bad args, 0 --help).
- Review fix: cents are bounded to |cents| <= 2**63-1. Importer `_to_cents` and cli `_parse_amount` guard `quantize` with `decimal.InvalidOperation -> ValueError`; importer errors surface as `line N: malformed amount ...` during parsing (before any DB write). Importer regexes use `re.ASCII`. CLI `budget set` accepts only `\d+(\.\d+)?` (ASCII, fullmatch; no sign/exponent), so `1e3` is now rejected; `250.000` OK, `250.001` rejected. `add_rule` (priority/min/max) and `set_budget` (amount) raise ValueError outside signed 64-bit; `cli.main` also catches OverflowError as a backstop.
