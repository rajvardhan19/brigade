# Piece 02: CSV importers (importers.py)
You are doing one piece of a larger job in this repository. Other pieces
run in separate sessions, so stay inside your piece.

Read first: .brigade/context.md, .brigade/progress.md, the "Spec" part 2 in
.brigade/plan.md, ledger/importers.py (stub + docstring) and ledger/db.py.
Do not explore beyond these; context.md is the map.

Your piece: implement `import_csv(conn, path, bank, account) -> (imported, skipped)`
exactly per spec part 2. Settled details (follow these, do not re-decide):
- Unknown bank -> ValueError before opening the file. A missing file lets the
  OSError (FileNotFoundError) propagate; do not wrap it.
- Open with `encoding="utf-8-sig", newline=""` and use `csv.reader`. Use
  `reader.line_num` for N in error messages (header is line 1). Skip fully
  blank rows. Format: `ValueError(f"line {N}: <reason>")`.
- Header must match the bank's columns exactly (after stripping each cell);
  otherwise ValueError mentioning `line 1`. Empty file -> ValueError `line 1`.
  A row with the wrong number of columns is malformed.
- Dates: validate with `datetime.datetime.strptime` (so 2024-02-30 fails);
  store as `YYYY-MM-DD`. acme `%Y-%m-%d`, zenith `%m/%d/%Y`.
- Money: `decimal.Decimal`, never float. Strip whitespace. At most 2 decimal
  places, otherwise malformed (no rounding). Convert with
  `int(d * 100)` after checking `d == d.quantize(Decimal("0.01"))`.
  Reject NaN/Infinity/empty. acme: signed plain decimal, no `$` or commas.
  zenith: optional leading `$`, commas as thousands separators (validate with
  a regex such as `^\$?\d{1,3}(,\d{3})*(\.\d{1,2})?$|^\$?\d+(\.\d{1,2})?$`);
  a minus sign is malformed. Exactly one of Debit/Credit non-empty (after
  strip); debit stored as negative, credit as positive.
- Description: `" ".join(desc.split())`.
- Atomicity: parse and validate EVERY row first; only if all are valid, insert.
  Wrap inserts in one transaction; on any exception `conn.rollback()` and
  re-raise; on success `conn.commit()`. Nothing from a bad file is stored.
- Duplicates: before inserting, load the set of (date, amount, description)
  already in the DB for this account. A parsed row whose key is in that set
  is skipped (counted). Do not add new rows to the set, so two identical rows
  in one file are both imported (if not already in the DB).
- New rows: category NULL, category_source NULL.

Write `tests/test_importers.py` (fixtures written to a TemporaryDirectory):
acme and zenith happy paths with exact cents (`-12.50` -> -1250,
`$1,234.56` debit -> -123456, credit positive), whitespace collapsing,
re-import gives (0, n), identical rows within one file both imported, a DB
row duplicated by two file rows -> both skipped, per-account dedup (same
file into another account imports all), unknown bank, bad date / bad amount
/ 3 decimals / zenith both-or-neither on line 3 -> message contains `line 3`
and DB still empty (also when earlier rows were valid), bad header -> `line 1`.

You own (may create or edit): ledger/importers.py, tests/test_importers.py,
.brigade/context.md (Decisions section, append only), .brigade/progress.md (append only).
Do not edit any other file. If you must, stop and explain why.
Must keep or provide: `importers.import_csv` signature from context.md; the
schema in context.md (do not change it).
Done when: `python3 -m unittest discover -s tests` passes with your new tests
running, and importing a malformed file leaves `list_transactions` empty.
Stop and report instead of guessing if: the spec and the settled details
above conflict, or you think the schema needs a change.

When finished, append to .brigade/progress.md:
## Piece 02: CSV importers
- Status: done | partial | blocked
- Files changed: ...
- Interface changes (also update context.md): ... or "none"
- Notes for later pieces: ...
- Check output (last lines): ...
