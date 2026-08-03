#!/usr/bin/env python
"""Stratified tool_dev/tool_eval split of ViSTR-Bench public (60/40, per task).

Output: configs/split.json  {task: {"dev": [ids], "eval": [ids]}}
Rule (per plan 三阶段): 禁止在同一批样本上同时调工具和汇报最终结果。
"""
import json
import os

import numpy as np

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(PROJ_DIR, "data", "benchmarks", "ViSTR-Bench-Public", "data.json")
OUT = os.path.join(PROJ_DIR, "configs", "split.json")
SEED = 20260802
DEV_FRAC = 0.6


def main():
    rows = json.load(open(BENCH))
    rng = np.random.default_rng(SEED)
    split = {}
    for r in rows:
        split.setdefault(r["task"], []).append(r["id"])
    out = {}
    n_dev = n_eval = 0
    for task, ids in sorted(split.items()):
        ids = sorted(ids)
        idx = rng.permutation(len(ids))
        k = max(1, int(round(len(ids) * DEV_FRAC)))
        dev = sorted(ids[i] for i in idx[:k])
        ev = sorted(ids[i] for i in idx[k:])
        out[task] = {"dev": dev, "eval": ev}
        n_dev += len(dev)
        n_eval += len(ev)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"seed={SEED} dev={n_dev} eval={n_eval} -> {OUT}")
    for t, v in out.items():
        print(f"  {t:24s} dev={len(v['dev']):3d} eval={len(v['eval']):3d}")


if __name__ == "__main__":
    main()
