# Brigade

A Claude Code skill for jobs too big for one session. It reads your project
goal, cuts the work into pieces that each fit in a fresh session, writes a
self-contained prompt for each piece, and picks the cheapest model that is
safe for that piece's risk. You run each piece in a new chat. The sessions
share state only through a few files in `.brigade/`.

It works on any Claude Code plan (Pro, Max, Team) and doesn't need an API key.

> **Before you rely on it, read the results.** Claude Code's default model
> built a five-module project in one session in under 3 minutes. Brigade
> recognized that each time, declined to split, and did the work itself at no
> measurable extra cost. When forced to split that same project, it worked
> end to end but cost **4.1× more**. Splitting is only likely to pay on jobs
> one session can't finish, such as multi-hour builds where the context fills
> up, and that case is **untested**. The fresh-context review is the part
> that measurably helped.

## Install

As a plugin (from inside Claude Code):

    /plugin marketplace add rajvardhan19/brigade
    /plugin install brigade@brigade

Then run `/brigade:plan <your goal, or a path to a spec file>`.

Or as a personal skill: copy `plugins/brigade/skills/plan` to
`~/.claude/skills/brigade`, and run `/brigade <goal>` and `/brigade next`
instead of the `/brigade:plan` forms below.

## How it works

1. **It decides whether to split, first and cheaply.** Every new session
   pays to start and has to learn the project again. If one session can do
   the job, Brigade says so and does the work in your current session. Then
   it writes an optional review prompt for a fresh session (see step 6). If
   you know better, for example because your usage window is short, ask it
   to split anyway: `/brigade:plan <goal>. Plan this as separate sessions.`
2. **It maps the project once** in `.brigade/context.md`: layout, commands,
   conventions, and the interfaces between parts. Every piece reads this map
   instead of exploring the code from scratch.
3. **It cuts pieces by file ownership, in waves.** No two pieces in a wave
   edit the same file. Wave 1 is usually the skeleton and the interfaces.
   Only the next wave gets full prompts; run `/brigade:plan next` when a wave
   is done, so later prompts match the code that actually exists.
4. **It picks a model by risk, not by task type.** For each piece it asks
   how bad a mistake would be, and whether the piece's check would catch it
   right away:

   | The piece is... | Model |
   |---|---|
   | Mechanical, fully specified, mistakes caught by its check | Haiku, low effort |
   | Bounded with a clear spec and a check that would catch a mistake | Sonnet, medium |
   | Auth, money, data, migrations, concurrency, interfaces others build on, or a mistake would go unnoticed | Opus, medium |

   A cheap model's mistakes are fine when they are cheap and caught at once:
   you rerun the piece one model up. They are costly when they are silent,
   because later pieces build on them. Brigade never picks Fable unless you
   ask, since Fable is billed to usage credits on Pro.
5. **Escalation is your job, with a fixed rule.** If a piece's check fails,
   rerun the same prompt one model up with the failure pasted in. Never retry
   on the same model twice.
6. **A fresh session reviews the work.** An Opus session that wrote none of
   the code reviews the diff. It ends with `VERDICT: CLEAN` or
   `VERDICT: DEFECTS` plus a ready-to-run fix prompt.

To start a piece, use a terminal:

    claude --model sonnet --effort medium "Do brigade piece 02: follow .brigade/prompts/02-importers.md"

Or, in VS Code or the desktop app, open a new chat, pick the model, and send
the same sentence.

## Measured results

All runs used Claude Code 2.1.321 on a Pro plan, with headless sessions in a
fresh copy of the project:

- **Baseline:** one session on Claude Code's Pro default (Opus 5.5, medium effort).
- **Brigade:** a planning session plus every session its plan calls for, run
  the way a user would, including escalation, reviews and `next`.

Correctness comes from hidden tests the sessions never saw. Cost is the
list-price figure Claude Code reports. It stands in for plan usage, and on a
subscription it isn't billed in money.

| Task | Skill version | Runs | Baseline | Brigade | Hidden tests | Split? |
|---|---|---|---|---|---|---|
| Password reset feature (auth) | draft | 1 | $0.31 | $0.35 (+11%) | all pass, both | No |
| Title length limit (control) | draft | 1 | $0.17 | $0.17 (0%) | all pass, both | No |
| Four features: sharing, history, export, login rate limiting | draft | 2 | $0.52, $0.54 | $0.58, $0.60 (+12%) | all pass, both | No |
| Greenfield build: storage, two bank importers, rules engine, budgets, CLI | current | 1 | $0.65, 2.4 min | $0.61, 2.1 min (−5%) | 32/32, both | No |
| Same build, split on request | current | 1 | $0.65, 2.4 min | **$2.66, 8.2 min (4.1×)** | 32/32, both | Yes: 10 sessions |

**Where the forced split's cost went:**

| Sessions | Cost |
|---|---|
| Three planning sessions (initial plan and two `next` runs) | $1.03 |
| One Opus skeleton piece | $0.31 |
| Four Sonnet pieces | $0.62 |
| Final review | $0.51 |
| Fix session | $0.19 |

The Sonnet pieces never needed escalation, so the self-contained prompts and
the shared `context.md` worked.

**What the fresh review caught.** The final review found five ways the build
broke the spec, such as oversized amounts crashing with a traceback where the
spec required a clean error. I then tested all three builds against those
five inputs:

| Build | Clean errors | Tracebacks | Wrongly accepted |
|---|---|---|---|
| One session, no skill | 1 | 3 | 1 (non-ASCII digits) |
| Brigade, not split | 1 | 3 | 1 |
| Brigade, split, after review and fix | 5 | 0 | 0 |

The hidden tests didn't cover these inputs, so all three builds scored 32/32.

**What this shows:**

1. On jobs up to a five-module greenfield build, one default session is the
   cheapest way to get working code. The current Brigade sees that and steps
   aside without measurable overhead.
2. Splitting a job that one session can do costs about 4× more, mostly in
   planning and review sessions.
3. The fresh-context review is what improved quality. Running it after a
   single session (Brigade writes that prompt for you) should cost roughly
   2× instead of 4×. That combination hasn't been measured on its own.

**What this doesn't show:** whether splitting pays on jobs that are too big
for one session. That is Brigade's main use case.

## Known limits

- **Splitting is only likely to help on very large jobs, and that's untested.**
- **Small sample:** 4 tasks and 11 runs in total, mostly single runs.
  Identical runs can differ by about ±20%. The robustness comparison comes
  from one split run.
- **You do the coordination:** starting sessions, picking models, merging
  parallel worktrees. The measurements don't count your time.
- **Overlap with Claude Code Projects:** Projects (beta, claude.ai/code and
  the desktop app) already splits work into fresh threads. It uses one thread
  model per project unless you ask for another in the task. Brigade adds a
  model choice per piece, and it works in the terminal and VS Code.
- **Prompts can go stale** if you skip `/brigade:plan next` between waves.

## Reproduce the benchmark

    python3 bench/run.py --tasks t6_ledger --arms baseline,brigade,brigade-forced --stage mine
    python3 bench/report.py mine

`bench/` contains the test projects, the task prompts, the hidden graders,
the first draft of the skill (`skill-v0`) and the raw results. Every headless
run counts against your plan's usage.

## License

MIT
