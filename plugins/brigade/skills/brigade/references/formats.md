# Brigade file formats

Keep every file short. Each session pays to read them.

## .brigade/context.md

    # Project context
    <One paragraph: what the project is and what this job adds.>

    ## Layout
    <Directory or file -> what lives there. Only what a piece needs.>

    ## Commands
    - Test: <exact command>
    - Build / lint / typecheck: <exact commands, if any>

    ## Conventions
    <Naming, error handling, how tests are written, anything a newcomer would get wrong.>

    ## Interfaces between parts
    <Function signatures, routes, data shapes and module boundaries that pieces
    rely on. This is the contract: a piece that changes it must update this
    section and say so in progress.md.>

    ## Decisions
    <One line per decision a later piece needs to know about. Pieces append here.>

## .brigade/plan.md

    # Plan: <goal in one line>
    Base commit: <sha, if git>
    Why split: <one or two sentences>

    ## Waves
    | Wave | Piece | Owns files | Model | Effort | Why this model |
    |---|---|---|---|---|---|
    | 1 | 01 skeleton | ... | opus | medium | defines interfaces every later piece uses |
    | 2 | 02 importer | ... | sonnet | medium | bounded, spec'd, tests catch mistakes |

    Later waves (outline only; `/brigade next` writes their prompts):
    - Wave 3: <one line each>

    ## How to run
    - Start a piece with:
      claude --model <model> --effort <effort> "Do brigade piece NN: follow .brigade/prompts/NN-slug.md"
      In VS Code or the desktop app: open a new chat, pick the model, send the same sentence.
    - Run the pieces in a wave one at a time. To run them in parallel instead,
      give each its own worktree (`claude --worktree NN-slug ...`) and merge
      them all before the next wave.
    - **If a piece's check fails** and its session can't fix it: rerun the same
      prompt in a new session one model up (haiku -> sonnet -> opus), and paste
      the failure output under the prompt. Never retry on the same model twice.
      If opus fails, stop and run `/brigade next` to re-plan.
    - **Review:** after any wave that had a high-damage piece, and always after
      the last wave, run that wave's review prompt in a new session on opus. If
      it says DEFECTS, run its fix prompt once.
    - When a wave is done, run `/brigade next` for the next one.
      (Installed as a plugin, the command is `/brigade:brigade next`.)

## .brigade/prompts/NN-slug.md (one per piece)

Fill in every line. A cheaper model needs a tighter spec.

    # Piece NN: <title>
    You are doing one piece of a larger job in this repository. Other pieces
    run in separate sessions, so stay inside your piece.

    Read first: .brigade/context.md, .brigade/progress.md, then <exact paths>.
    Do not explore beyond these unless you need to; context.md is the map.

    Your piece: <exactly what to build or change>
    You own (may create or edit): <exact paths>
    Do not edit any other file. If you must, stop and explain why.
    Must keep or provide: <interfaces from context.md this piece implements or relies on>
    Done when: <exact command> passes, and <observable result>.
    Stop and report instead of guessing if: <specific conditions>.

    When finished, append to .brigade/progress.md:
    ## Piece NN: <title>
    - Status: done | partial | blocked
    - Files changed: ...
    - Interface changes (also update context.md): ... or "none"
    - Notes for later pieces: ...
    - Check output (last lines): ...

## .brigade/prompts/review-wN.md (and review-final.md)

    # Review: <wave N | final>
    You are reviewing work done by other sessions. You did not write it; judge it.
    Read .brigade/plan.md, .brigade/context.md and .brigade/progress.md, then the
    full diff since <base commit or wave start>. Run <all checks>.
    Look for: requirements missed, contracts in context.md broken, pieces that
    disagree with each other, security and data-loss problems, and tests that
    pass without testing anything.
    List each defect with file:line and why it matters. Do not fix anything.
    End with exactly one line: VERDICT: CLEAN or VERDICT: DEFECTS.
    If DEFECTS, follow it with a self-contained fix prompt in a fenced block
    and the line: Fix with: claude --model <sonnet, or opus if any defect is
    high-damage> --effort medium

## Standalone review (when the job was not split)

There is no plan.md or context.md, so the prompt has to carry the goal
itself. Write it to `.brigade/prompts/review-final.md`:

    # Review
    You are reviewing a change another session made. You did not write it; judge it.
    The goal was:
    <the user's goal, verbatim or closely summarized, including every stated requirement>
    Read the full diff since <base commit, or "the last commit" if git>, then run <all checks>.
    Look for: requirements missed, inputs the code doesn't handle (empty, huge,
    malformed, non-ASCII), errors that leak tracebacks or secrets, security and
    data-loss problems, and tests that pass without testing anything.
    List each defect with file:line and why it matters. Do not fix anything.
    End with exactly one line: VERDICT: CLEAN or VERDICT: DEFECTS.
    If DEFECTS, follow it with a self-contained fix prompt in a fenced block
    and the line: Fix with: claude --model <sonnet, or opus if any defect is
    high-damage> --effort medium
