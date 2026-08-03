#!/usr/bin/env python
"""Driving-task evidence computation + threshold tuning (dev) / blind test (eval).

Usage:
  /opt/conda/bin/python -u agent/eval_motion.py --compute          # evidence cache
  /opt/conda/bin/python -u agent/eval_motion.py --tune             # sweep on dev, report eval
"""
import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tools import BENCH_DIR
from agent.tools.motion import analyze_motion

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJ_DIR, "outputs", "tool_runs", "driving_motion.jsonl")
SPLIT = json.load(open(os.path.join(PROJ_DIR, "configs", "split.json")))
TASKS = ["Vehicle_Movement", "Relative_Velocity"]


def _one(args):
    r, colors = args
    try:
        ev = analyze_motion(os.path.join(BENCH_DIR, r["video"]), colors=colors)
        return {"id": r["id"], "task": r["task"], "gt": r["answer"],
                "status": ev["status"], "data": ev["data"]}
    except Exception as e:
        return {"id": r["id"], "task": r["task"], "gt": r["answer"],
                "status": "failed", "data": {"error": str(e)[:200]}}


def compute():
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    rows = [r for r in rows if r["task"] in TASKS]
    done = set()
    if os.path.exists(CACHE):
        for l in open(CACHE):
            done.add(json.loads(l)["id"])
    todo = [r for r in rows if r["id"] not in done]
    print(f"evidence todo={len(todo)}/{len(rows)}", flush=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    args = [(r, ("green",) if r["task"] == "Vehicle_Movement" else ("green", "blue"))
            for r in todo]
    with open(CACHE, "a") as f, ProcessPoolExecutor(8) as ex:
        for i, res in enumerate(ex.map(_one, args), 1):
            f.write(json.dumps(res) + "\n")
            f.flush()
            if i % 20 == 0:
                print(f"  [{i}/{len(todo)}]", flush=True)
    print("compute done", flush=True)


def decide_vehicle(d, thr):
    c = d["data"]["colors"].get("green", {})
    if "resid_center_mag_mean" not in c:
        return None
    return "Yes" if c["resid_center_mag_mean"] > thr else "No"


def decide_relvel(d, w_loom):
    g, b = d["data"]["colors"].get("green", {}), d["data"]["colors"].get("blue", {})
    if "resid_center_mag_mean" not in g or "resid_center_mag_mean" not in b:
        return None
    sg = g["resid_center_mag_mean"] + w_loom * g.get("loom_rate", 0)
    sb = b["resid_center_mag_mean"] + w_loom * b.get("loom_rate", 0)
    return "Green" if sg > sb else "Blue"


def tune():
    rows = [json.loads(l) for l in open(CACHE)]
    split = json.load(open(os.path.join(PROJ_DIR, "configs", "split.json")))
    for r in rows:
        r["split"] = "dev" if r["id"] in set(SPLIT[r["task"]]["dev"]) else "eval"
    base = json.load(open(os.path.join(PROJ_DIR, "configs", "baseline_direct.json")))

    def acc(samples, fn, p):
        ok = tot = 0
        for s in samples:
            if s["status"] == "failed":
                a = base.get(str(s["id"]), {}).get("answer")
            else:
                a = fn(s, p)
                if a is None:
                    a = base.get(str(s["id"]), {}).get("answer")
            if a is None:
                continue
            tot += 1
            ok += (a == s["gt"])
        return 100 * ok / max(1, tot)

    for task, fn, grid, name in [
        ("Vehicle_Movement", decide_vehicle, np.linspace(0.05, 1.5, 30), "resid_mag thr"),
        ("Relative_Velocity", decide_relvel, np.linspace(0, 2.0, 21), "w_loom"),
    ]:
        dev = [r for r in rows if r["task"] == task and r["split"] == "dev"]
        ev = [r for r in rows if r["task"] == task and r["split"] == "eval"]
        best = max(grid, key=lambda p: acc(dev, fn, p))
        base_dev = 100 * sum(base[str(s["id"])]["correct"] for s in dev) / len(dev)
        base_ev = 100 * sum(base[str(s["id"])]["correct"] for s in ev) / len(ev)
        print(f"\n[{task}] n_dev={len(dev)} n_eval={len(ev)}")
        print(f"  baseline: dev={base_dev:.1f} eval={base_ev:.1f}")
        print(f"  tool: best {name}={best:.3f} -> dev={acc(dev, fn, best):.1f} "
              f"eval={acc(ev, fn, best):.1f}")
        # confusion at best
        for sp, ss in [("dev", dev), ("eval", ev)]:
            stats = {}
            for s in ss:
                a = fn(s, best) if s["status"] != "failed" else None
                a = a or base.get(str(s["id"]), {}).get("answer")
                stats[(s["gt"], a)] = stats.get((s["gt"], a), 0) + 1
            print(f"    {sp} confusion (gt,pred): {dict(sorted(stats.items()))}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--compute", action="store_true")
    ap.add_argument("--tune", action="store_true")
    args = ap.parse_args()
    if args.compute:
        compute()
    if args.tune:
        tune()
