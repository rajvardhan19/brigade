# Example: what Brigade produced for a real build

These are the unedited files Brigade wrote while building `ledger`, a
personal-finance toolkit (SQLite storage, two bank CSV importers, a
categorization rules engine, budgets and reports, and a CLI). This run
was asked to split. The project brief is [`bench/tasks/t6_ledger.md`](../../bench/tasks/t6_ledger.md).

| File | What it is |
|---|---|
| [plan.md](plan.md) | Waves, file ownership, model and effort per piece, the reason for each model, and the rules for running pieces |
| [context.md](context.md) | The 77-line project map every session reads instead of re-reading the code |
| [prompts/](prompts/) | One self-contained prompt per piece. [02-importers.md](prompts/02-importers.md) shows how much gets settled up front so a cheaper model can't go wrong |
| [progress.md](progress.md) | What each session reported when it finished: files changed, interface changes, test output |
| [review-final-output.md](review-final-output.md) | The fresh-context review: five spec violations found, then a ready-to-run fix prompt |

Result: 10 sessions, 4 of 5 build pieces on Sonnet with no escalations, and
all 32 hidden tests passing. The review's five defects were fixed. It cost
4.1x a single session, because one session could have built this. See the
main README for the full numbers.
