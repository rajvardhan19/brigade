---
name: brigade
description: Plan a large project or a big multi-part change as a series of fresh Claude Code sessions. Each session gets a self-contained prompt and the cheapest model that is safe for its risk. Use when a job is too big for one session. Run it with "next" to write the next wave of prompts from the progress so far.
argument-hint: "[project goal, or path to a spec file] | next"
disable-model-invocation: true
---

# Brigade: run a large job as a series of fresh sessions

You are the planner. Decide whether this job should be split. If it should,
write one prompt per piece of work. The user runs each piece in a new session
on the model you name. Sessions share nothing except the files in `.brigade/`
and the code itself.

Input: $ARGUMENTS

If the input is `next` or `continue`, skip to **Next wave** below. If it is a
path to a file, read that file as the goal.

## 1. Decide whether to split. Do this first, and cheaply.

Splitting is not free. Every new session pays to start and has to learn the
project again. On jobs that one session can finish, splitting only adds cost.
In this skill's own tests, a single default session (Opus 5.5 at medium) built
four features in a 600-line project in 7 turns and under 2 minutes. Using this
skill there cost 11-12% more and gave the same result.

Before exploring, judge the size from the goal and the top level of the file
tree. Split only when at least one of these holds:

- One session would need more than about an hour, or would fill its context
  and compact. Typical cases are a greenfield build with several subsystems,
  a large migration, or a change across many modules.
- The job has three or more parts that can be built against agreed interfaces
  in separate files, and some of those parts are routine enough for a cheaper
  model.

Otherwise do not split. Say so in one line, then do the work yourself in this
session. You have already started reading the code, and a handoff would make
a new session read it all again.

When you finish, write `.brigade/prompts/review-final.md` using the
"standalone review" format in `${CLAUDE_SKILL_DIR}/references/formats.md`.
Tell the user that running it in a new session on opus is optional, and
recommended when the work touched anything high-damage (see step 4). A
reviewer that didn't write the code catches what the author can't see. In
this skill's tests, a fresh review found five spec violations that both
single-session builds had missed.

If the user explicitly asks for a split (for example, "plan this as separate
sessions"), split even if one session could do the job. They may know
something you don't, such as a short usage window. Note in plan.md that the
split was on request.

## 2. Map the project once, for every session

Fresh sessions are cheap only if they don't have to rediscover the project.
Write `.brigade/context.md`: what the project is, its layout, the commands
that build and test it, its conventions, and the interfaces between the
parts. Every prompt tells its session to read this file first instead of
exploring. For a greenfield project, the first piece builds the skeleton
(layout, interface stubs, test harness) and completes context.md.

## 3. Cut pieces along file ownership, in waves

- **Each piece owns a set of files.** No two pieces in the same wave touch the
  same file. Shared files such as routers, registries and config belong to one
  piece, or to a small "integrate" piece at the end of the wave. Two sessions
  editing the same file is where split work breaks.
- **Size each piece to fit one session comfortably:** one subsystem with a
  check that fails loudly when it's wrong. If a piece has no such check, make
  writing one part of the piece.
- **Group pieces into waves by dependency.** Wave 1 is usually the skeleton
  and the interfaces. Later waves fill in modules behind those interfaces.
  Keep a wave to four pieces or fewer.
- **Write full prompts only for the next wave.** List later waves as one-line
  outlines. Prompts written before the code exists go stale, so later waves
  get written by running this skill again with `next` once the earlier ones
  are done: `/brigade next`, or `/brigade:brigade next` with the plugin install.

## 4. Pick a model and effort for each piece by risk

Ask two questions about each piece:

1. **How bad is a mistake?** Low means local, cosmetic and easy to revert.
   High means security, auth, permissions, money, data loss, migrations,
   concurrency, or an interface that other pieces build on. A wrong interface
   gets copied into every piece that comes after it.
2. **How fast would a mistake be noticed?** Fast means the piece's done-check
   fails loudly. Slow means only a careful reader, or production, would notice.

A cheap model is fine when its mistakes are cheap and caught right away: the
escalation rule reruns the piece one tier up, and the waste is one retry. A
cheap model is expensive when its mistakes are silent, because later pieces
build on them and the cost shows up late.

| The piece is... | Model | Effort |
|---|---|---|
| Mechanical and fully specified, with any mistake caught by its check | haiku | low |
| Bounded, with a clear spec and a check that would catch a mistake | sonnet | medium |
| High damage, or a mistake would be silent, or the design is open, or it defines interfaces others use | opus | medium (high only when a mistake would be silent) |

Use only haiku, sonnet and opus unless the user asks for Fable. On Pro plans,
Fable is billed to usage credits.

## 5. Write the files

Read `${CLAUDE_SKILL_DIR}/references/formats.md`, then write:

- `.brigade/context.md`, the project map
- `.brigade/plan.md`, with the goal, the waves, the routing table and the rules for the user
- `.brigade/prompts/NN-slug.md`, one per piece in the next wave, plus the review prompt for that wave if it needs one
- `.brigade/progress.md`, a heading only; each session adds to it

## 6. Report

Print a short table (wave, piece, model, effort, one-line reason), then the
exact command for the first piece, for example:

    claude --model sonnet --effort medium "Do brigade piece 01: follow .brigade/prompts/01-skeleton.md"

In VS Code or the desktop app, the user opens a new chat, picks the model, and
sends the same sentence. Do not start any piece yourself.

## Next wave

1. Read `.brigade/plan.md`, `.brigade/progress.md`, `.brigade/context.md` and
   any review results. Run the project's checks.
2. If the last wave left failing checks or unfinished pieces, write fix prompts
   for those first, applying the escalation rule.
3. Update context.md wherever the code now differs from it, and adjust the
   remaining outline if what was built changed the plan.
4. Write full prompts for the next wave, and report as in step 6.
5. If every wave is done, write the final review prompt and report it.
