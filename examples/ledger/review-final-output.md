# Final review (fresh Opus session, verbatim output)

I followed `.brigade/prompts/review-final.md`. All 67 tests pass, and the normal CLI flow works. With an acme file and a zenith file, the second import reports `Imported 0, skipped 3`, `$1,234.56` is stored as -123456 cents, the report shows `Food 70.50 50.00 -20.50 OVER`, and errors for a missing file, a directory, a bad regex or a bad month print cleanly. The problem is very large numbers: they fall outside the error handling and the CLI prints a traceback, which the spec forbids.

**Defects**

1. **`ledger/importers.py:55-58`**: an acme amount with 29 or more digits (e.g. `99999999999999999999999999999.00`) passes the regex. Then `d.quantize(Decimal("0.01"))` raises `decimal.InvalidOperation`, which is not a `ValueError` and has no `line N`. This breaks spec part 2. The CLI also prints a traceback (`decimal.InvalidOperation`, exit 1), which breaks spec part 5.
2. **`ledger/importers.py:119-123`**: a 20- to 28-digit amount parses fine, but the INSERT raises `OverflowError: Python int too large to convert to SQLite INTEGER`. The rollback works and nothing is imported (I checked). Still, the error is not a `ValueError` with `line N`, and the CLI shows a traceback. Amounts outside the 64-bit range should be rejected during parsing, with the line number.
3. **`ledger/cli.py:51`**: `budget set Food 2024-01 1e30` gives a `decimal.InvalidOperation` traceback from `quantize`. `context.md` says "`decimal.InvalidOperation` is converted to ValueError", but that only happens when the `Decimal` is created at line 44.
4. **`ledger/cli.py:72-74,128`**: `rule add X --contains y --priority 99999999999999999999` (or the same with `--min`/`--max`) gives an `OverflowError` traceback from sqlite. The `except` at line 128 doesn't catch `OverflowError`, and `add_rule`/`set_budget` don't check the range.
5. **`ledger/importers.py:29-33`** (minor): `\d` without `re.ASCII` matches non-ASCII digits, and `Decimal` accepts them. So the acme amount `-١٢.50` (Arabic-Indic digits) is imported as -1250 instead of being rejected as malformed.
6. **`ledger/cli.py:41-53`** (minor): `budget set` accepts scientific notation (`1e3` gives a $1000.00 budget). The spec only shows dollar forms like `250` and `250.00`.
7. **Test gaps**: no test covers very large amounts in the importer, `budget set` or `rule add`, or non-ASCII digits. That's why the 67 passing tests didn't catch defects 1–5.

These checks hold: decimals parsed with `Decimal` (no floats), negative formatting, duplicates judged against the database before the import, the import being all-or-nothing, rule priority and ties going to the earlier rule, hand-set categories surviving `--all`, and the report edge cases. The tests are real tests, not ones that pass without checking anything.

VERDICT: DEFECTS

```
Fix brigade review defects in the `ledger` package (stdlib Python 3 only). Read .brigade/plan.md
("Spec" is the source of truth) and .brigade/context.md first. Do not change public signatures.

Defects to fix:
1. ledger/importers.py `_to_cents` (lines ~51-58): huge amounts (e.g. acme
   `99999999999999999999999999999.00`) make `d.quantize(...)` raise decimal.InvalidOperation,
   and 20-28 digit amounts parse but then raise OverflowError on the SQLite INSERT
   (lines ~119-123). Both must instead raise ValueError("line N: malformed amount ...") during
   parsing, before any DB write. Reject any cents value whose absolute value exceeds
   2**63 - 1 (and guard quantize with try/except decimal.InvalidOperation -> ValueError).
2. ledger/importers.py regexes (lines ~29-33): add re.ASCII to _ACME_AMOUNT, _ZENITH_AMOUNT,
   _ACME_DATE and _ZENITH_DATE so non-ASCII digits (e.g. Arabic-Indic) are malformed.
3. ledger/cli.py `_parse_amount` (lines ~41-53): `budget set Food 2024-01 1e30` raises
   decimal.InvalidOperation from quantize -> traceback. Wrap quantize in try/except, reject
   values whose cents exceed 2**63 - 1, and accept only plain dollar forms: use a regex
   like r"\d+(\.\d+)?" with re.ASCII + fullmatch (no exponent, no sign); keep the existing
   rule that `250.000` is accepted and `250.001` rejected.
4. ledger/rules.py add_rule and ledger/budgets.py set_budget: raise ValueError when
   priority/min_amount/max_amount/amount fall outside the signed 64-bit range
   (-2**63 .. 2**63-1), so `ledger rule add X --contains y --priority 99999999999999999999`
   prints `error: ...` and exits 1 instead of an OverflowError traceback. Also add
   OverflowError to the caught exceptions in ledger/cli.py main (line ~128) as a backstop.

Add tests: importer rows with 20-digit and 29-digit amounts raise ValueError containing the
right `line N` and import nothing; an acme amount with Arabic-Indic digits is rejected; CLI
`budget set` with `1e30` and `1e3` fails with a stderr message and no traceback; CLI
`rule add` with a huge --priority/--min fails cleanly; add_rule/set_budget raise ValueError
on out-of-range ints.

Check: `python3 -m unittest discover -s tests` passes, and each of the commands above
prints `error: ...` to stderr with exit code 1 and no traceback. Record decisions in
.brigade/context.md (Decisions) and a short entry in .brigade/progress.md.
```

Fix with: claude --model sonnet --effort medium