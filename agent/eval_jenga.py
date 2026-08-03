#!/usr/bin/env python
"""Compute Jenga evidence + feature separation check (dev/eval)."""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tools import BENCH_DIR
from agent.tools.jenga import analyze_jenga

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJ_DIR, "outputs", "tool_runs", "jenga.jsonl")


def _one(r):
    try:
        ev = analyze_jenga(os.path.join(BENCH_DIR, r["video"]))
        return {"id": r["id"], "task": r["task"], "gt": r["answer"],
                "status": ev["status"], "data": ev["data"]}
    except Exception as e:
        return {"id": r["id"], "task": r["task"], "gt": r["answer"],
                "status": "failed", "data": {"error": str(e)[:200]}}


if __name__ == "__main__":
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    rows = [r for r in rows if r["task"] == "Jenga_Stability"]
    done = set()
    if os.path.exists(CACHE):
        for l in open(CACHE):
            done.add(json.loads(l)["id"])
    todo = [r for r in rows if r["id"] not in done]
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "a") as f, ProcessPoolExecutor(8) as ex:
        for i, res in enumerate(ex.map(_one, todo), 1):
            f.write(json.dumps(res) + "\n")
            f.flush()
            if i % 10 == 0:
                print(f"[{i}/{len(todo)}]", flush=True)
    rows = [json.loads(l) for l in open(CACHE)]
    ok = [r for r in rows if r["status"] == "success"]
    print(f"success={len(ok)}/{len(rows)}")
    feats = ["n_rows", "target_row_from_top", "blocks_above_overlap",
             "tower_lean_px", "target_protrusion_px", "tower_wobble_px"]
    for gt in ["Yes", "No"]:
        sub = [r for r in ok if r["gt"] == gt]
        print(f"GT={gt} (n={len(sub)}):")
        for f_ in feats:
            v = [r["data"].get(f_, np.nan) for r in sub]
            print(f"  {f_:24s} p25/50/75={np.nanpercentile(v, [25, 50, 75]).round(2)}")
