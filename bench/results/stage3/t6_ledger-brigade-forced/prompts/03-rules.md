# Piece 03: categorization rules (rules.py)
You are doing one piece of a larger job in this repository. Other pieces
run in separate sessions, so stay inside your piece.

Read first: .brigade/context.md, .brigade/progress.md, the "Spec" part 3 in
.brigade/plan.md, ledger/rules.py (stub + docstring) and ledger/db.py.
Do not explore beyond these; context.md is the map.

Your piece: implement `add_rule`, `categorize`, `set_category` exactly per
spec part 3, using the `rules` table and `transactions.category_source`.
Settled details (follow these, do not re-decide):
- add_rule: ValueError if both `contains` and `pattern` are None or empty;
  ValueError if `pattern` does not compile (`re.error`); ValueError if
  min_amount > max_amount when both given. Store and commit; return
  `cursor.lastrowid`.
- Matching: `contains.casefold() in description.casefold()`;
  `re.search(pattern, description, re.IGNORECASE)`; min/max compared
  inclusively against `abs(amount)`. A rule must satisfy all its conditions.
- Rule order: `ORDER BY priority DESC, id ASC`; the first matching rule wins.
- categorize(recategorize=False): candidate transactions are those with
  `category_source IS NULL`; with recategorize=True, also `= 'rule'`.
  `'manual'` is never touched. For each candidate with a winning rule: if its
  category differs from the current one, or the source is NULL, set
  category and `category_source='rule'` and count it as changed. A candidate
  with no matching rule is left exactly as it is (keeps an earlier rule
  category). Return the count. Commit once at the end.
- set_category(conn, transaction_id, category): sets category and
  `category_source='manual'`; ValueError if no transaction has that id.
  Commit.

Write `tests/test_rules.py` (insert transactions with raw SQL on the schema
in context.md, using `connect(":memory:")`): add_rule validation errors,
contains and pattern case-insensitivity, min/max inclusive on abs value for
both spending and income, all-conditions-must-hold, priority wins, tie ->
lower id wins, default run skips already-categorized rows, recategorize
recomputes rule rows after a higher-priority rule is added, unmatched rows
keep their category, manual category survives `categorize(recategorize=True)`
even when a rule matches, return value counts only actual changes (a second
run returns 0), set_category on unknown id raises.

You own (may create or edit): ledger/rules.py, tests/test_rules.py,
.brigade/context.md (Decisions section, append only), .brigade/progress.md (append only).
Do not edit any other file. If you must, stop and explain why.
Must keep or provide: `rules.*` signatures from context.md; the schema in
context.md (do not change it).
Done when: `python3 -m unittest discover -s tests` passes with your new tests running.
Stop and report instead of guessing if: the spec and the settled details
above conflict, or you think the schema needs a change.

When finished, append to .brigade/progress.md:
## Piece 03: categorization rules
- Status: done | partial | blocked
- Files changed: ...
- Interface changes (also update context.md): ... or "none"
- Notes for later pieces: ...
- Check output (last lines): ...
