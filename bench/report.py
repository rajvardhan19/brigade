#!/usr/bin/env python3
"""Print a markdown table from bench/results/<stage>/*/summary.json.

Usage: python3 bench/report.py stage1 [stage2 ...]
"""
import json
import pathlib
import sys

RESULTS = pathlib.Path(__file__).resolve().parent / "results"
REPS_SEEN = {}


def load(stages):
    rows = []
    for stage in stages:
        for f in sorted((RESULTS / stage).glob("*/summary.json")):
            rows.append(json.loads(f.read_text()))
    return rows


def models(s):
    seen = {}
    for sess in s["session_log"]:
        for m, u in sess["model_usage"].items():
            short = m.replace("claude-", "").replace("-5-5", "")
            seen[short] = seen.get(short, 0) + (u.get("costUSD") or 0)
    return ", ".join(f"{m} ${c:.2f}" for m, c in sorted(seen.items(), key=lambda kv: -kv[1]))


def main():
    rows = load(sys.argv[1:] or ["stage1"])
    for s in rows:
        if s.get('rep', 1) > 1:
            REPS_SEEN[s['task']] = True
    print("| Task | Arm | Cost (list $) | Session time | Sessions | Turns | Hidden tests | Visible tests | Spend by model | Notes |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for s in rows:
        h, v = s["hidden_tests"], s["visible_tests"]
        hid = f"{h['ran'] - h['failed']}/{h['ran']}"
        vis = f"{v['ran'] - v['failed']}/{v['ran']}"
        notes = "; ".join(s["notes"]) if s["notes"] else ""
        if s["plan"].get("routing"):
            reviews = s["plan"].get("reviews")
            if reviews:
                s["plan"]["review_verdict"] = ", ".join(f"{n.removesuffix('.md')}={v}" for n, v in reviews)
            notes = ("plan: " + ", ".join(f"{n}.{t[:18]}={m}/{e}" for n, t, m, e in s["plan"]["routing"])
                     + (f"; review={s['plan'].get('review_verdict')}" if s["plan"].get("review_verdict") else "")
                     + ("; " + notes if notes else ""))
        print(f"| {s['task']} | {s['arm']}{'-r' + str(s['rep']) if s.get('rep') and REPS_SEEN.get(s['task']) else ''} | ${s['cost_usd']:.2f} | {s['session_wall_s'] / 60:.1f} min | "
              f"{s['sessions']} | {s['turns']} | {hid} | {vis} | {models(s)} | {notes} |")


if __name__ == "__main__":
    main()
