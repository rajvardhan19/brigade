#!/usr/bin/env python3
"""A/B benchmark: one default Claude Code session vs. the brigade skill.

baseline: one headless session on Claude Code's Pro default (Opus 5.5, medium effort) gets the task.
brigade:  a planning session runs `/brigade <task>` on the same default. If it writes .brigade/plan.md,
          each piece runs in its own fresh session on the model and effort the plan names, the way a
          user following the plan would. The skill's escalation rule is applied (if the visible tests
          fail after a piece, rerun it one model up with the failure output), then the Review piece,
          then one fix session if the review says DEFECTS. If the skill decides not to split, the
          planning session does the work itself and nothing else runs.

Every session is a fresh `claude -p` process: no shared conversation, like a new chat.
Correctness is judged by hidden tests the sessions never see (bench/hidden/), copied in afterwards.

Usage: python3 bench/run.py --tasks t1_reset,t4_title --stage stage1 [--arms baseline,brigade] [--workers 4]
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

BENCH = pathlib.Path(__file__).resolve().parent
ROOT = BENCH.parent
SKILL = pathlib.Path(os.environ.get("BRIGADE_SKILL", ROOT / "plugins" / "brigade" / "skills" / "brigade"))  # bench/skill-v0 = first draft
SCRATCH = pathlib.Path(os.environ.get("BENCH_SCRATCH", "/tmp/brigade-bench"))
CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"

DEFAULT_MODEL, DEFAULT_EFFORT = "opus", "medium"  # Claude Code default on Pro since v2.1.280 (model-config docs)
TIERS = ["haiku", "sonnet", "opus"]
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
SESSION_TIMEOUT_S = 30 * 60
SESSION_BUDGET_USD = "5"
REPS = 1
CMD_RE = re.compile(r"claude\s+--model\s+([\w.\-\[\]]+)\s+--effort\s+(\w+)")
FENCE_RE = re.compile(r"```[^\n]*\n(.*?)\n\s*```", re.S)


def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def claude(prompt, cwd, model, effort, log_dir, label):
    """Run one fresh headless session. Returns (record, result_text)."""
    cmd = [CLAUDE, "-p", prompt, "--model", model, "--effort", effort,
           "--output-format", "json", "--no-session-persistence", "--strict-mcp-config",
           "--setting-sources", "project,local", "--permission-mode", "auto",
           "--permission-prompts", "none", "--max-budget-usd", SESSION_BUDGET_USD]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=SESSION_TIMEOUT_S, stdin=subprocess.DEVNULL)
        try:
            data = json.loads(p.stdout)
        except json.JSONDecodeError:
            data = {"is_error": True, "result": p.stdout[-3000:], "stderr": p.stderr[-3000:]}
    except subprocess.TimeoutExpired:
        data = {"is_error": True, "result": "TIMEOUT"}
    wall = time.time() - t0
    (log_dir / f"{label}.json").write_text(json.dumps(data, indent=1))
    usage = {}
    for m, u in (data.get("modelUsage") or {}).items():
        usage[m] = {k: u.get(k) for k in ("inputTokens", "outputTokens", "cacheReadInputTokens",
                                           "cacheCreationInputTokens", "costUSD")}
    rec = {
        "label": label, "model": model, "effort": effort, "wall_s": round(wall, 1),
        "cost_usd": round(data.get("total_cost_usd") or 0.0, 4), "turns": data.get("num_turns"),
        "is_error": bool(data.get("is_error")), "subtype": data.get("subtype"),
        "permission_denials": len(data.get("permission_denials") or []),
        "subagents_spawned": (data.get("subagent_stats") or {}).get("spawned"),
        "model_usage": usage,
    }
    return rec, data.get("result") or ""


def run_tests(cwd, pattern="test_*.py"):
    if not (pathlib.Path(cwd) / "tests").is_dir():
        return {"ok": True, "ran": 0, "failed": 0, "tail": "(no tests/ directory yet)"}
    p = sh([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", pattern], cwd, timeout=300)
    out = p.stdout + p.stderr
    ran = re.search(r"Ran (\d+) test", out)
    failed = re.search(r"FAILED \(([^)]*)\)", out)
    return {"ok": p.returncode == 0, "ran": int(ran.group(1)) if ran else 0,
            "failed": sum(int(x) for x in re.findall(r"=(\d+)", failed.group(1))) if failed else 0,
            "tail": out[-1500:]}


FIXTURES = {"t6_ledger": "fixture-empty"}


def setup_repo(run_dir, with_skill, fixture="fixture"):
    if run_dir.exists():
        shutil.rmtree(run_dir)
    shutil.copytree(BENCH / fixture, run_dir, ignore=shutil.ignore_patterns("__pycache__"))
    if with_skill:
        shutil.copytree(SKILL, run_dir / ".claude" / "skills" / "brigade")
    (run_dir / ".gitignore").write_text("__pycache__/\n")
    git = ["git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid"]
    sh(["git", "init", "-q", "-b", "main"], run_dir)
    sh(git + ["add", "-A"], run_dir)
    sh(git + ["commit", "-q", "-m", "base"], run_dir)
    return sh(["git", "rev-parse", "HEAD"], run_dir).stdout.strip()


def parse_plan(text):
    parts = re.split(r"(?m)^##\s+(\d+)\.\s+(.*)$", text)
    pieces, problems = [], []
    for i in range(1, len(parts), 3):
        num, title, body = int(parts[i]), parts[i + 1].strip(), parts[i + 2]
        cmd, fence = CMD_RE.search(body), FENCE_RE.search(body)
        if not cmd or not fence:
            problems.append(f"piece {num} '{title}': could not find start command or prompt block")
            continue
        pieces.append({"num": num, "title": title, "model": cmd.group(1), "effort": cmd.group(2),
                       "prompt": fence.group(1).strip()})
    return pieces, problems


def safe_model(model, notes):
    if model in TIERS:
        return model
    notes.append(f"plan named model '{model}'; ran it on opus instead (Fable bills credits on Pro)")
    return "opus"


def safe_effort(effort, notes):
    if effort in EFFORTS:
        return effort
    notes.append(f"plan named effort '{effort}'; used medium")
    return "medium"


FORCE_SPLIT = "\n\nPlan this as separate sessions even if one session could do it."


def brigade_pipeline(task_text, run_dir, log_dir, sessions, notes, force=False):
    rec, _ = claude("/brigade " + task_text + (FORCE_SPLIT if force else ""), run_dir, DEFAULT_MODEL, DEFAULT_EFFORT, log_dir, "plan")
    sessions.append(rec)
    plan_path = run_dir / ".brigade" / "plan.md"
    if not plan_path.exists():
        notes.append("skill chose NOT to split: the planning session did the work itself")
        return {"split": False}
    if (run_dir / ".brigade" / "prompts").is_dir():
        return brigade_waves(run_dir, log_dir, sessions, notes)
    shutil.copy(plan_path, log_dir / "plan.md")
    pieces, problems = parse_plan(plan_path.read_text())
    notes.extend(problems)
    if not pieces:
        notes.append("plan had no runnable pieces; stopped")
        return {"split": True, "pieces": 0}
    review = [p for p in pieces if p["title"].lower().startswith("review")]
    work = [p for p in pieces if p not in review]
    plan_info = {"split": True, "pieces": len(work),
                 "routing": [(p["num"], p["title"], p["model"], p["effort"]) for p in pieces]}

    for piece in work:
        model = safe_model(piece["model"], notes)
        effort = safe_effort(piece["effort"], notes)
        prompt = piece["prompt"]
        while True:
            rec, _ = claude(prompt, run_dir, model, effort, log_dir, f"piece{piece['num']}-{model}")
            rec["piece"] = piece["num"]
            sessions.append(rec)
            check = run_tests(run_dir)
            if check["ok"]:
                break
            if model == "opus":
                notes.append(f"piece {piece['num']} still failing on opus; stopping (escalation rule)")
                return plan_info
            nxt = TIERS[TIERS.index(model) + 1]
            notes.append(f"piece {piece['num']} failed visible tests on {model}; escalating to {nxt}")
            model = nxt
            prompt = (piece["prompt"] + "\n\nA previous attempt at this piece ended with these failing "
                      "checks:\n```\n" + check["tail"][-1200:] + "\n```")

    for piece in review:
        rec, out = claude(piece["prompt"], run_dir, safe_model(piece["model"], notes),
                          safe_effort(piece["effort"], notes), log_dir, "review")
        sessions.append(rec)
        (log_dir / "review.txt").write_text(out)
        verdict = re.search(r"VERDICT:\s*(CLEAN|DEFECTS)", out)
        plan_info["review_verdict"] = verdict.group(1) if verdict else "MISSING"
        if verdict and verdict.group(1) == "DEFECTS":
            after = out[verdict.end():]
            fence, cmd = FENCE_RE.search(after), CMD_RE.search(after)
            fix_prompt = fence.group(1).strip() if fence else (
                "Fix these defects found in a code review, then rerun the tests:\n\n" + out)
            fmodel = safe_model(cmd.group(1), notes) if cmd else "opus"
            feffort = safe_effort(cmd.group(2), notes) if cmd else "medium"
            rec, _ = claude(fix_prompt, run_dir, fmodel, feffort, log_dir, f"fix-{fmodel}")
            sessions.append(rec)
    return plan_info


LIMIT_WORDS = ("usage limit", "rate limit", "limit reached", "out of credits", "credit balance")


def hit_limit(rec, text):
    blob = (text or "").lower()
    return rec["is_error"] and any(w in blob for w in LIMIT_WORDS)


def parse_routing(plan_text):
    """Map piece number ('01') and review names to (model, effort) from plan.md tables."""
    routing = {}
    for line in plan_text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip().strip("`*") for c in line.strip().strip("|").split("|")]
        idx = next((i for i, c in enumerate(cells) if c.lower() in TIERS + ["fable"]), None)
        if idx is None:
            continue
        model = cells[idx].lower()
        effort = cells[idx + 1].lower() if idx + 1 < len(cells) else "medium"
        for c in cells[:idx]:
            m = re.match(r"^(\d{2})\b", c)
            if m:
                routing[m.group(1)] = (model, effort)
                break
            if "review" in c.lower():
                routing[c.lower()] = (model, effort)
                break
    return routing


def run_piece_with_escalation(nn, name, model, effort, run_dir, log_dir, sessions, notes):
    base_prompt = f"Do brigade piece {nn}: follow .brigade/prompts/{name}"
    prompt = base_prompt
    while True:
        rec, out = claude(prompt, run_dir, model, effort, log_dir, f"piece{nn}-{model}")
        rec["piece"] = nn
        sessions.append(rec)
        if hit_limit(rec, out):
            notes.append(f"usage limit hit during piece {nn}; stopped")
            return "limit"
        check = run_tests(run_dir)
        if check["ok"]:
            return "ok"
        if model == "opus":
            notes.append(f"piece {nn} still failing on opus; stopping (escalation rule)")
            return "failed"
        nxt = TIERS[TIERS.index(model) + 1]
        notes.append(f"piece {nn} failed tests on {model}; escalating to {nxt}")
        model = nxt
        prompt = (base_prompt + "\n\nA previous attempt at this piece ended with these failing checks:\n```\n"
                  + check["tail"][-1200:] + "\n```")


def brigade_waves(run_dir, log_dir, sessions, notes, max_rounds=6):
    bdir = run_dir / ".brigade"
    done, ran, reviews = set(), [], []
    for rnd in range(max_rounds):
        new = sorted(p.name for p in (bdir / "prompts").glob("*.md") if p.name not in done)
        if not new:
            notes.append(f"round {rnd}: planner wrote no new prompts; finished")
            break
        routing = parse_routing((bdir / "plan.md").read_text())
        work = [n for n in new if not n.lower().startswith("review")]
        revs = [n for n in new if n.lower().startswith("review")]
        for name in work:
            nn = name[:2]
            model, effort = routing.get(nn, (None, None))
            if model is None:
                notes.append(f"no routing row for piece {nn}; ran it on opus medium")
                model, effort = "opus", "medium"
            model, effort = safe_model(model, notes), safe_effort(effort, notes)
            ran.append((nn, name, model, effort))
            status = run_piece_with_escalation(nn, name, model, effort, run_dir, log_dir, sessions, notes)
            done.add(name)
            if status != "ok":
                return {"split": True, "pieces": len(ran), "routing": ran, "reviews": reviews, "stopped": status}
        for name in revs:
            key = name.lower().removesuffix(".md")
            model, effort = routing.get(key, ("opus", "medium"))
            model, effort = safe_model(model, notes), safe_effort(effort, notes)
            rec, out = claude(f"Run the brigade review: follow .brigade/prompts/{name}", run_dir, model, effort,
                              log_dir, f"{key}")
            sessions.append(rec)
            (log_dir / f"{key}.txt").write_text(out)
            done.add(name)
            verdict = re.search(r"VERDICT:\s*(CLEAN|DEFECTS)", out)
            reviews.append((name, verdict.group(1) if verdict else "MISSING"))
            if verdict and verdict.group(1) == "DEFECTS":
                after = out[verdict.end():]
                fence, cmd = FENCE_RE.search(after), CMD_RE.search(after)
                fix = fence.group(1).strip() if fence else "Fix these review defects, then rerun the tests:\n\n" + out
                fm = safe_model(cmd.group(1), notes) if cmd else "opus"
                fe = safe_effort(cmd.group(2), notes) if cmd else "medium"
                rec, _ = claude(fix, run_dir, fm, fe, log_dir, f"fix-{key}-{fm}")
                sessions.append(rec)
        if any(n.lower().startswith("review-final") for n in revs):
            break
        rec, out = claude("/brigade next", run_dir, DEFAULT_MODEL, DEFAULT_EFFORT, log_dir, f"plan-next{rnd + 1}")
        sessions.append(rec)
        if hit_limit(rec, out):
            notes.append("usage limit hit during planning; stopped")
            break
    else:
        notes.append("hit the round cap")
    shutil.copy(bdir / "plan.md", log_dir / "plan.md")
    if (bdir / "context.md").exists():
        shutil.copy(bdir / "context.md", log_dir / "context.md")
    pdir = log_dir / "prompts"
    pdir.mkdir(exist_ok=True)
    for p in (bdir / "prompts").glob("*.md"):
        shutil.copy(p, pdir / p.name)
    return {"split": True, "pieces": len(ran), "routing": ran, "reviews": reviews}


def run_one(task, arm, stage, rep=1):
    task_text = (BENCH / "tasks" / f"{task}.md").read_text().strip()
    name = f"{task}-{arm}" + (f"-r{rep}" if rep > 1 or REPS > 1 else "")
    run_dir = SCRATCH / stage / name
    log_dir = BENCH / "results" / stage / name
    if log_dir.exists():
        shutil.rmtree(log_dir)
    log_dir.mkdir(parents=True)
    base = setup_repo(run_dir, with_skill=arm.startswith("brigade"), fixture=FIXTURES.get(task, "fixture"))
    sessions, notes, plan_info = [], [], {}
    t0 = time.time()
    if arm == "baseline":
        rec, _ = claude(task_text, run_dir, DEFAULT_MODEL, DEFAULT_EFFORT, log_dir, "baseline")
        sessions.append(rec)
    else:
        plan_info = brigade_pipeline(task_text, run_dir, log_dir, sessions, notes, force=(arm == "brigade-forced"))
    elapsed = time.time() - t0

    progress = run_dir / ".brigade" / "progress.md"
    if progress.exists():
        shutil.copy(progress, log_dir / "progress.md")
    diff = sh(["git", "diff", base, "--", ".", ":(exclude).brigade"], run_dir).stdout
    untracked = sh(["git", "ls-files", "--others", "--exclude-standard", "--", ".", ":(exclude).brigade"], run_dir).stdout
    (log_dir / "diff.patch").write_text(diff + ("\n# untracked files:\n" + untracked if untracked else ""))
    for f in untracked.split():
        if f.endswith(".py"):
            (log_dir / ("new_" + f.replace("/", "__"))).write_text((run_dir / f).read_text())

    visible = run_tests(run_dir)
    (run_dir / "tests").mkdir(exist_ok=True)
    shutil.copy(BENCH / "hidden" / f"hidden_test_{task}.py", run_dir / "tests")
    hidden = run_tests(run_dir, "hidden_test_*.py")
    summary = {
        "task": task, "arm": arm, "rep": rep, "stage": stage, "when": datetime.datetime.now().isoformat(timespec="seconds"),
        "cost_usd": round(sum(s["cost_usd"] for s in sessions), 4),
        "session_wall_s": round(sum(s["wall_s"] for s in sessions), 1),
        "pipeline_wall_s": round(elapsed, 1),
        "sessions": len(sessions), "turns": sum(s["turns"] or 0 for s in sessions),
        "visible_tests": {k: visible[k] for k in ("ok", "ran", "failed")},
        "hidden_tests": {k: hidden[k] for k in ("ok", "ran", "failed")},
        "hidden_tail": hidden["tail"] if not hidden["ok"] else "",
        "any_session_error": any(s["is_error"] for s in sessions),
        "plan": plan_info, "notes": notes, "session_log": sessions,
    }
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--arms", default="baseline,brigade")
    ap.add_argument("--stage", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--reps", type=int, default=1)
    args = ap.parse_args()
    global REPS
    REPS = args.reps
    jobs = [(t, a, r) for r in range(1, args.reps + 1) for t in args.tasks.split(",") for a in args.arms.split(",")]
    print(f"claude={CLAUDE}\nscratch={SCRATCH}\njobs={jobs}", flush=True)
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_one, t, a, args.stage, r): (t, f"{a}-r{r}") for t, a, r in jobs}
        for fut in cf.as_completed(futs):
            t, a = futs[fut]
            try:
                s = fut.result()
                print(f"DONE {t}/{a}: ${s['cost_usd']} {s['session_wall_s']}s sessions={s['sessions']} "
                      f"hidden={s['hidden_tests']} notes={s['notes']}", flush=True)
            except Exception as e:  # keep other jobs going
                print(f"CRASH {t}/{a}: {e!r}", flush=True)


if __name__ == "__main__":
    main()
