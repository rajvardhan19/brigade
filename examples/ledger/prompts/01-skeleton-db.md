# Piece 01: package skeleton and storage (db.py)
You are doing one piece of a larger job in this repository. Other pieces
run in separate sessions, so stay inside your piece.

Read first: .brigade/context.md, .brigade/progress.md, then the "Spec"
section of .brigade/plan.md (parts 1-5; you implement part 1 and stub the rest).
The repo is otherwise empty; there is nothing else to explore.

Your piece:
1. Create the package `ledger/` with `__init__.py`, and `__main__.py` that runs
   `raise SystemExit(main(sys.argv[1:]))` from `ledger.cli`.
2. Implement `ledger/db.py` fully: `connect(path)` creates the three tables
   from context.md "Interfaces" with `CREATE TABLE IF NOT EXISTS` (works for
   ":memory:" and file paths; reconnecting keeps data), and
   `list_transactions(conn, account=None)` returning plain dicts with exactly
   the keys id, account, date, description, amount, category, ordered by
   date then id. Do not expose `category_source` in the dicts.
   You may adjust the schema if you find a real problem with it, but then
   update context.md "Interfaces" and say why in progress.md.
3. Create stub modules `ledger/importers.py`, `ledger/rules.py`,
   `ledger/budgets.py`, `ledger/cli.py` with the exact signatures in
   context.md, each body `raise NotImplementedError`. Add a short docstring
   to each stub quoting its spec part so later pieces see the contract.
4. Write `tests/test_db.py`: schema creation, reconnect to the same temp file
   keeps rows, list_transactions ordering (date then id, including same-date
   ties) and account filter, category None when unset, exact dict keys.
5. Confirm/complete context.md: fix anything in Layout/Interfaces that
   differs from what you built; add Decisions lines for anything a later
   piece must know (e.g. whether `conn.row_factory` is set — prefer NOT
   setting it on the returned connection, so other modules see tuples
   unless they set their own cursor's row_factory; record whichever you pick).

You own (may create or edit): ledger/__init__.py, ledger/__main__.py,
ledger/db.py, ledger/importers.py, ledger/rules.py, ledger/budgets.py,
ledger/cli.py (stubs only), tests/test_db.py, .brigade/context.md,
.brigade/progress.md (append only).
Do not edit any other file. If you must, stop and explain why.
Must keep or provide: every signature in context.md "Interfaces"; standard
library only.
Done when: `python3 -m unittest discover -s tests` passes with your db tests
running (not 0 tests), and `python3 -c "import ledger.importers, ledger.rules, ledger.budgets, ledger.cli"` succeeds.
Stop and report instead of guessing if: the spec seems to require a schema
feature you cannot express in the three tables, or a signature in context.md
conflicts with the spec.

When finished, append to .brigade/progress.md:
## Piece 01: package skeleton and storage
- Status: done | partial | blocked
- Files changed: ...
- Interface changes (also update context.md): ... or "none"
- Notes for later pieces: ...
- Check output (last lines): ...
