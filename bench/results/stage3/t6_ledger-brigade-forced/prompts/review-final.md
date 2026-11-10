# Review: final
You are reviewing work done by other sessions. You did not write it; judge it.
Read .brigade/plan.md (the "Spec" section is the source of truth),
.brigade/context.md and .brigade/progress.md, then the full diff since base
commit 96af3e9 (`git diff 96af3e9` plus untracked files under ledger/ and tests/).
Run `python3 -m unittest discover -s tests`, and exercise the CLI by hand
(`python3 -m ledger --db <tmp> ...`) with an acme and a zenith CSV.
Look for: spec requirements missed (go through parts 1-5 line by line),
contracts in context.md broken, pieces that disagree with each other, money
handled as float or rounded wrongly (cents, `$1,234.56`, negative formatting),
non-atomic imports, wrong duplicate semantics, rule precedence or manual-category
overrides, report edge cases, tracebacks leaking from the CLI, and tests that
pass without testing anything.
List each defect with file:line and why it matters. Do not fix anything.
End with exactly one line: VERDICT: CLEAN or VERDICT: DEFECTS.
If DEFECTS, follow it with a self-contained fix prompt in a fenced block
and the line: Fix with: claude --model <sonnet, or opus if any defect is
high-damage> --effort medium
