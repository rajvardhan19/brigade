---
name: brigade
description: Split a project goal into self-contained prompts, one per fresh Claude Code session, each with the model and effort it should run on. Use when the user asks to plan a multi-part change for separate sessions or chats.
disable-model-invocation: true
argument-hint: "<the project goal or prompt, or a path to a file holding it>"
---

# Brigade: plan the work, write one prompt per session

You plan; you implement only if you decide not to split (Step 2). Read
the goal, look at the project, and produce a short ordered list of prompts. The user runs each one in a NEW
session on the model you name. Each session starts with zero context, so
every prompt must stand on its own.

Goal: $ARGUMENTS

## Step 1: Look before planning (keep it cheap)

List the file tree, read the README/manifest and the files the goal
obviously touches, and find the test/build/typecheck commands. Do not read
the whole codebase. If the project is a git repo, note the current commit
as the base.

## Step 2: Decide whether to split at all

Every new session re-reads the project, so splitting has a cost. Do NOT
split when any of these hold. Instead, say in one line why, then do the
work yourself in this session (you have already read the files, so this
is the cheapest path). Create no plan files.

- The whole job is one concern a single session would finish quickly.
- The pieces cannot be separated by files (each would need to edit the
  same files as the others).
- Every piece would need Opus anyway: splitting then buys only fresh
  context, which matters only if the job is large.

Split when the pieces own separate files AND at least one piece can run
on a cheaper model, or when the job is big enough that one session's
context would grow large. Aim for 2-5 pieces. Fewer is better.

## Step 3: Pick a model for each piece by risk

Ask two questions about each piece:

1. **How bad is a mistake?** Low: local, cosmetic, easy to revert. High:
   auth, permissions, secrets, money, data deletion, migrations,
   concurrency, or an interface other pieces build on.
2. **How fast would a mistake be noticed?** Fast: a test, build or
   typecheck in the piece's done-check fails loudly. Slow: only a careful
   human, or production, would notice.

| Mistake is... | Model | Effort |
|---|---|---|
| Low damage and caught fast, work is mechanical and fully specified | haiku | low |
| Low damage, or caught fast, with a clear spec | sonnet | medium |
| High damage, or would go unnoticed, or cause unknown, or design is ambiguous | opus | medium (high only if a mistake would be silent) |

Use only haiku, sonnet and opus. Never assign Fable unless the user asks:
on Pro it is billed to usage credits.

## Step 4: Write the plan file

Create `.brigade/plan.md` and `.brigade/progress.md` (progress starts with just
a heading). In plan.md write the goal, the base commit, one line on why
you split this way, then for each piece, in the order to run them:

    ## <n>. <title>
    Run in: a new session · model: <model> · effort: <effort>
    Start with: claude --model <model> --effort <effort>
    Why this model: <damage if wrong> / <how a mistake would be caught>
    Depends on: <piece numbers or "none">

    ```
    <the prompt, using the template below>
    ```

Run pieces one at a time in the listed order. Do not plan parallel runs:
two sessions editing one folder overwrite each other.

Prompt template (fill every line; a lower-tier model needs a tighter spec):

    You are doing one piece of a larger change in this repository. Other
    pieces are done in separate sessions.
    Whole change: <one or two sentences>
    Your piece: <exactly what to do>
    Read first: .brigade/progress.md, <exact paths>
    You may change: <exact paths>. Do not edit other files; if you must,
    stop and explain why instead.
    Must keep or provide: <function signatures, routes, data shapes other
    pieces rely on>
    Done when: <exact command> passes, and <observable result>.
    Stop and report instead of guessing if: <specific conditions>.
    When finished: append to .brigade/progress.md your piece number, files
    changed, any decision later pieces need, and the last lines of the
    done-check output.

## Step 5: Add the review and the escalation rule

The last piece is always titled "Review", in the same format, on opus at
medium effort. A fresh session that never saw the work catches what the
workers were blind to. Its prompt:

    Review the change for: <goal>. Read .brigade/plan.md and
    .brigade/progress.md, then the full diff from <base commit>. Run
    <all checks>. List defects with file:line and why each matters. Do
    not fix anything. End with exactly one line: VERDICT: CLEAN or
    VERDICT: DEFECTS. If DEFECTS, after it give a self-contained fix
    prompt in a fenced block and a line "Fix with: claude --model
    <sonnet, or opus if any defect is in a high-damage area> --effort
    medium".

End plan.md with this rule for the user: if a piece's done-check fails
and its session cannot fix it, start a new session one model up (haiku
→ sonnet → opus) with the same prompt plus the failure output. Do not
retry on the same model twice. If opus fails, stop and rethink the split.
If the review says DEFECTS, run its fix prompt once in a new session.

## Step 6: Report

In chat, print a short table (piece, model, effort, one-line reason) and
the path to `.brigade/plan.md`. Do not start any piece yourself.
