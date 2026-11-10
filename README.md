# Brigade

**Plan big Claude Code jobs the way a kitchen brigade runs a service:** one
planner, a station for each part of the work, the right cook at each
station, and a final check before anything leaves the pass.

Brigade is a Claude Code skill. Give it your project goal and it decides
whether the job needs more than one session. If it does, it cuts the work
into pieces that each fit in a fresh session, writes a self-contained prompt
for each piece, and picks the cheapest model that is safe for that piece's
risk. Every job ends with a review prompt for a fresh session that didn't
write the code.

It works on any Claude Code plan (Pro, Max, Team), in the terminal and in
VS Code, and it doesn't need an API key.

## Why use it

Every claim below comes from measured runs; the numbers are in
[Measured results](#measured-results).

### 1. A reviewer that finds the bugs your session shipped

One session that writes code and then checks its own work shares its own
blind spots. Brigade finishes every job by handing you a review prompt for
a fresh session that never saw the code being written. When it splits a job,
the review is a required step of the plan. In our test build of a finance toolkit,
that review found **five ways the code broke the spec**. For example,
oversized amounts crashed with a traceback where the spec required a clean
error, and non-ASCII digits were accepted as money. I tested all three
builds against those five inputs:

| Build | Clean errors | Tracebacks or bad data accepted |
|---|---|---|
| One normal Claude Code session | 1 of 5 | **4 of 5** |
| Brigade (split run), after its review and fix | **5 of 5** | 0 of 5 |

The project's own tests passed in every build, so none of these problems
would have shown up as a failure. [Read the review it wrote](examples/ledger/review-final-output.md).

### 2. It knows when not to bother

Splitting a job has a cost: each new session has to start up and learn the
project. Brigade checks first. On every job one session could handle, up to
a five-module greenfield build, it said so and did the work itself (7 of 7
runs). The current version did this at no measurable extra cost (−5% in one
run; the first draft cost 11–12% more). Then it left you a review prompt to
run if the work was risky. Trying it on a job that turns out to be small
costs you about nothing.

### 3. Plans that cheaper models can carry out

When a job is too big for one session, Brigade gives you a plan built for
handoffs:

- **A project map** (`context.md`, 77 lines in the example) that every
  session reads instead of re-reading the codebase.
- **Pieces cut by file ownership**, so two sessions never edit the same file.
- **Prompts that settle the hard details up front.** The importer prompt
  pinned down money parsing, line numbers in errors, atomic imports and
  duplicate rules before a cheaper model touched them.
  [See the prompt](examples/ledger/prompts/02-importers.md).

In the example build, **all four pieces given to Sonnet passed first time,
with no escalations.**

### 4. A model for each piece, chosen by risk

For each piece, Brigade asks how bad a mistake would be and whether a test
would catch it right away. Auth, money, data, migrations and the interfaces
other pieces depend on go to Opus. Bounded pieces with a clear spec and
tests go to Sonnet or Haiku. Each choice is written down with its reason in
[plan.md](examples/ledger/plan.md), so you can check it.

### 5. Your project's state lives on disk

The plan, the project map and a progress log all live in `.brigade/`. You
can stop between any two pieces, for example when you hit your plan's usage
window, and pick up later with `/brigade:plan next`. You can also hand the
remaining pieces to a teammate. Nothing depends on one long conversation
surviving.

## What it won't do

- **It won't make jobs cheaper that one session can do.** When we forced it
  to split a build that one session could finish in 2.4 minutes, it cost
  4.1× more, mostly in planning and review sessions. Brigade won't split
  such jobs unless you ask.
- **Savings on very large jobs are unproven.** Multi-hour builds where one
  session's context fills up are where splitting should pay. That's the
  case Brigade is built for, and it hasn't been measured yet.
- **You coordinate.** You start each session and pick its model, and
  Brigade tells you exactly what to run.

## Install

As a plugin (from inside Claude Code):

    /plugin marketplace add rajvardhan19/brigade
    /plugin install brigade@brigade

Then run `/brigade:plan <your goal, or a path to a spec file>`.

Or as a personal skill: copy `plugins/brigade/skills/plan` to
`~/.claude/skills/brigade`, and run `/brigade <goal>` and `/brigade next`
instead of the `/brigade:plan` forms below.

## How it works

1. **It decides whether to split.** If one session can do the job, Brigade
   does it in your current session and writes an optional review prompt. To
   split anyway, add "Plan this as separate sessions" to your goal.
2. **It maps the project once** in `.brigade/context.md`: layout, commands,
   conventions, and the interfaces between parts.
3. **It cuts pieces by file ownership, in waves.** Wave 1 is usually the
   skeleton and the interfaces. Only the next wave gets full prompts. Run
   `/brigade:plan next` after each wave, so later prompts match the code
   that actually exists.
4. **It picks a model by risk:**

   | The piece is... | Model |
   |---|---|
   | Mechanical, fully specified, mistakes caught by its check | Haiku, low effort |
   | Bounded with a clear spec and a check that would catch a mistake | Sonnet, medium |
   | Auth, money, data, migrations, concurrency, interfaces others build on, or a mistake would go unnoticed | Opus, medium |

   It never picks Fable unless you ask, because Fable is billed to usage
   credits on Pro.
5. **It escalates on a fixed rule.** If a piece's check fails, rerun the same
   prompt one model up with the failure pasted in. Never retry on the same
   model twice.
6. **A fresh Opus session reviews the work.** It ends with `VERDICT: CLEAN`
   or `VERDICT: DEFECTS` plus a ready-to-run fix prompt.

To start a piece, use a terminal:

    claude --model sonnet --effort medium "Do brigade piece 02: follow .brigade/prompts/02-importers.md"

Or, in VS Code or the desktop app, open a new chat, pick the model, and send
the same sentence.

**See a full real run:** [examples/ledger](examples/ledger) has the plan,
the project map, every prompt, the progress log and the review, exactly as
Brigade wrote them.

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
| Same build, split on request | current | 1 | $0.65, 2.4 min | $2.66, 8.2 min (4.1×) | 32/32, both | Yes: 10 sessions |

**Where the forced split's cost went:**

| Sessions | Cost |
|---|---|
| Three planning sessions | $1.03 |
| One Opus skeleton piece | $0.31 |
| Four Sonnet pieces | $0.62 |
| Final review | $0.51 |
| Fix session | $0.19 |

**Robustness on the review's five inputs** (two oversized amounts, non-ASCII
digits, an exponent-style budget, and an out-of-range priority):

| Build | Clean errors | Tracebacks | Wrongly accepted |
|---|---|---|---|
| One session, no skill | 1 | 3 | 1 |
| Brigade, not split (before the optional review) | 1 | 3 | 1 |
| Brigade, split, after review and fix | 5 | 0 | 0 |

**Takeaways:**

1. On jobs up to a five-module greenfield build, one default session is the
   cheapest way to get code that passes its tests. Brigade sees that and
   steps aside.
2. The fresh-context review is what raised quality. Running it after a
   single session should cost roughly 2× instead of 4×. That combination
   hasn't been measured on its own yet.
3. Whether splitting saves usage on jobs that are too big for one session is
   untested.

## Known limits

- **Small sample:** 4 tasks and 11 runs in total, mostly single runs.
  Identical runs can differ by about ±20%. The robustness comparison comes
  from one split run.
- **Overlap with Claude Code Projects:** Projects (beta, claude.ai/code and
  the desktop app) already splits work into fresh threads. It uses one thread
  model per project unless you ask for another in the task. Brigade adds a
  model choice per piece, the review step, and support for the terminal and
  VS Code.
- **Prompts can go stale** if you skip `/brigade:plan next` between waves.

## Reproduce the benchmark

    python3 bench/run.py --tasks t6_ledger --arms baseline,brigade,brigade-forced --stage mine
    python3 bench/report.py mine

`bench/` contains the test projects, the task prompts, the hidden graders,
the first draft of the skill (`skill-v0`) and the raw results. Every headless
run counts against your plan's usage.

## License

MIT
