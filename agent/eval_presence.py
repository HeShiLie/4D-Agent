#!/usr/bin/env python
"""Compute presence evidence for Vehicle_Movement + tune threshold."""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tools import BENCH_DIR
from agent.tools.presence import analyze_presence

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJ_DIR, "outputs", "tool_runs", "vehicle_presence.jsonl")


def _one(r):
    try:
        ev = analyze_presence(os.path.join(BENCH_DIR, r["video"]))
        return {"id": r["id"], "task": r["task"], "gt": r["answer"],
                "status": ev["status"], "data": ev["data"]}
    except Exception as e:
        return {"id": r["id"], "task": r["task"], "gt": r["answer"],
                "status": "failed", "data": {"error": str(e)[:200]}}


if __name__ == "__main__":
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    rows = [r for r in rows if r["task"] == "Vehicle_Movement"]
    done = set()
    if os.path.exists(CACHE):
        for l in open(CACHE):
            done.add(json.loads(l)["id"])
    todo = [r for r in rows if r["id"] not in done]
    print(f"todo={len(todo)}", flush=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "a") as f, ProcessPoolExecutor(8) as ex:
        for i, res in enumerate(ex.map(_one, todo), 1):
            f.write(json.dumps(res) + "\n")
            f.flush()
            if i % 10 == 0:
                print(f"[{i}/{len(todo)}]", flush=True)
    # quick separation check
    rows = [json.loads(l) for l in open(CACHE)]
    ok = [r for r in rows if "presence_median" in r["data"]]
    for gt in ["Yes", "No"]:
        v = [r["data"]["presence_median"] for r in ok if r["gt"] == gt]
        print(f"GT={gt} n={len(v)} p10/25/50/75/90="
              f"{np.percentile(v, [10, 25, 50, 75, 90]).round(3)}")
