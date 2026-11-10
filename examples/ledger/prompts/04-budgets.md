# Piece 04: budgets and monthly report (budgets.py)
You are doing one piece of a larger job in this repository. Other pieces
run in separate sessions, so stay inside your piece.

Read first: .brigade/context.md, .brigade/progress.md, the "Spec" part 4 in
.brigade/plan.md, ledger/budgets.py (stub + docstring) and ledger/db.py.
Do not explore beyond these; context.md is the map.

Your piece: implement `set_budget` and `monthly_report` exactly per spec part 4.
Settled details (follow these, do not re-decide):
- Month must match `^\d{4}-(0[1-9]|1[0-2])$`, else ValueError (both functions).
- set_budget: amount must be an `int` (not bool) and >= 0, else ValueError.
  Use `INSERT ... ON CONFLICT(category, month) DO UPDATE` (or INSERT OR
  REPLACE). Commit.
- monthly_report: spending = transactions with `amount < 0` and
  `date LIKE 'YYYY-MM-%'` (all accounts). Group by
  `COALESCE(category, 'Uncategorized')`; spent = -SUM(amount) (positive int).
  Rows = union of categories with spending this month and categories with a
  budget this month. A category with only income and no budget does not
  appear. A budget set for the literal category "Uncategorized" merges with
  uncategorized spending. budget = None if unset; remaining = budget - spent
  or None; over = budget is not None and spent > budget (spent == budget is
  not over; spent with no budget is not over). Sort by category with Python
  `sorted` on the name. All money values are ints.

Write `tests/test_budgets.py` (insert transactions with raw SQL, using
`connect(":memory:")`): budget replace, month validation, spent ignores
income and other months (e.g. 2024-03 vs 2024-03-31 vs 2024-04-01), sums
across accounts, Uncategorized row, budget with no spending -> spent 0,
remaining negative and over True when overspent, equal -> over False,
no-budget -> budget/remaining None and over False, sort order, exact dict keys.

You own (may create or edit): ledger/budgets.py, tests/test_budgets.py,
.brigade/context.md (Decisions section, append only), .brigade/progress.md (append only).
Do not edit any other file. If you must, stop and explain why.
Must keep or provide: `budgets.*` signatures from context.md; the schema in
context.md (do not change it).
Done when: `python3 -m unittest discover -s tests` passes with your new tests running.
Stop and report instead of guessing if: the spec and the settled details
above conflict, or you think the schema needs a change.

When finished, append to .brigade/progress.md:
## Piece 04: budgets and monthly report
- Status: done | partial | blocked
- Files changed: ...
- Interface changes (also update context.md): ... or "none"
- Notes for later pieces: ...
- Check output (last lines): ...
