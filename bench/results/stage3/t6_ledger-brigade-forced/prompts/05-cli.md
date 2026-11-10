# Piece 05: command line (cli.py)
You are doing one piece of a larger job in this repository. Other pieces
run in separate sessions, so stay inside your piece.

Read first: .brigade/context.md, .brigade/progress.md, the "Spec" part 5 in
.brigade/plan.md, ledger/cli.py (stub + docstring), ledger/__main__.py, and
only the signatures/docstrings of ledger/{db,importers,rules,budgets}.py.
Do not explore beyond these; context.md is the map. Do not change those modules.

Your piece: implement `main(argv)` per spec part 5 with argparse, wiring the
existing library functions. Settled details (follow these, do not re-decide):
- Parser: `--db PATH` is a required top-level option (before the subcommand);
  subcommands are required: `import`, `rule add`, `categorize`, `budget set`,
  `report`. `--min/--max/--priority` are `type=int`.
- argparse errors call sys.exit: wrap `parse_args` in `try/except SystemExit as e`
  and `return e.code` (2 for bad args, 0 for `--help`). main never raises SystemExit.
- Open the db with `db.connect(args.db)` and close it in `finally`.
- Catch `(ValueError, OSError, csv.Error, sqlite3.Error)` around connect and
  the command: print `error: <message>` to stderr, return 1. No traceback ever.
  (importer lets FileNotFoundError and csv.Error propagate; UnicodeDecodeError
  is a ValueError.)
- `budget set` AMOUNT: parse with `decimal.Decimal` (never float); reject
  non-finite, negative, or more than 2 decimal places (`250.001`) with an
  error -> return 1; cents = int(amount * 100). `250`, `250.0`, `250.00` all = 25000.
- Money formatting helper `_fmt(cents)`: None -> `-`; else sign + `%d.%02d`
  of abs value, e.g. 12345 -> `123.45`, -1000 -> `-10.00`, -50 -> `-0.50`,
  0 -> `0.00`. Integer arithmetic only.
- `report MONTH`: for each row print
  `"\t".join([category, _fmt(spent), _fmt(budget), _fmt(remaining)])`, plus
  `"\tOVER"` when `row["over"]`. No header line. Empty report prints nothing, returns 0.
- Success output goes to stdout via print; return 0.

Write `tests/test_cli.py`: call `main([...])` with stdout/stderr captured via
`contextlib.redirect_stdout/redirect_stderr`, db and CSV files in a
`tempfile.TemporaryDirectory()`. Cover: import acme then same file again
(`Imported N, skipped 0` then `Imported 0, skipped N`); zenith import; rule add
prints `Rule 1 added` then `Rule 2 added`; categorize and `--all`; budget set
with `250`, `250.00`, and bad `12.345`/`abc`/`-5`; report lines exact (tabs,
`-` for None, negative remaining, OVER column); errors return non-zero with
stderr message and no "Traceback": missing file, unknown bank, malformed CSV
(message contains `line N`), missing `--db`, unknown subcommand, bad month,
rule add without --contains/--pattern. One test runs
`python3 -m ledger --db X report 2024-01` via subprocess (sys.executable,
cwd = repo root) and checks exit code 0.

You own (may create or edit): ledger/cli.py, tests/test_cli.py,
.brigade/context.md (Decisions section, append only), .brigade/progress.md (append only).
Do not edit any other file. If you must, stop and explain why.
Must keep or provide: `cli.main(argv) -> int`; all other signatures in context.md unchanged.
Done when: `python3 -m unittest discover -s tests` passes (all 53 prior tests
plus yours), and `python3 -m ledger --db /nonexistent-dir/x.db report 2024-01`
prints an error to stderr with no traceback and exits non-zero.
Stop and report instead of guessing if: a library function behaves differently
from context.md, or a spec requirement needs a change outside cli.py.

When finished, append to .brigade/progress.md:
## Piece 05: command line
- Status: done | partial | blocked
- Files changed: ...
- Interface changes (also update context.md): ... or "none"
- Notes for later pieces: ...
- Check output (last lines): ...
