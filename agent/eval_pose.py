#!/usr/bin/env python
"""Compute pose evidence for Rotation_Direction + Fall_Direction; learn option mapping on dev.

MUST run under: /opt/conda/envs/python3.10.13/bin/python (torch+ROCm+ultralytics)
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tools import BENCH_DIR
from agent.tools.pose_motion import analyze_fall, analyze_rotation

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJ_DIR, "outputs", "tool_runs", "pose_motion.jsonl")


def main():
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    done = set()
    if os.path.exists(CACHE):
        for l in open(CACHE):
            done.add(json.loads(l)["id"])
    todo = [r for r in rows if r["task"] in ("Rotation_Direction", "Fall_Direction")
            and r["id"] not in done]
    print(f"todo={len(todo)}", flush=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "a") as f:
        for i, r in enumerate(todo, 1):
            try:
                if r["task"] == "Rotation_Direction":
                    ev = analyze_rotation(os.path.join(BENCH_DIR, r["video"]))
                else:
                    ev = analyze_fall(os.path.join(BENCH_DIR, r["video"]))
                rec = {"id": r["id"], "task": r["task"], "gt": r["answer"],
                       "options": r["options"], "question": r["direct_prompting"],
                       "status": ev["status"], "data": ev["data"]}
            except Exception as e:
                rec = {"id": r["id"], "task": r["task"], "gt": r["answer"],
                       "options": r["options"], "question": r["direct_prompting"],
                       "status": "failed", "data": {"error": str(e)[:200]}}
            f.write(json.dumps(rec) + "\n")
            f.flush()
            if i % 10 == 0 or i == len(todo):
                print(f"[{i}/{len(todo)}]", flush=True)
    report()


def report():
    split = json.load(open(os.path.join(PROJ_DIR, "configs", "split.json")))
    base = json.load(open(os.path.join(PROJ_DIR, "configs", "baseline_direct.json")))
    rows = [json.loads(l) for l in open(CACHE)]

    # ---- Rotation: feature vel_sum sign -> CW/CCW mapping per perspective
    rot = [r for r in rows if r["task"] == "Rotation_Direction"
           and r["status"] == "success"]
    print(f"\n[Rotation] success={len(rot)}/{sum(1 for r in rows if r['task']=='Rotation_Direction')}")

    def persp(q):
        if "top-down" in q:
            return "top"
        if "viewer's" in q:
            return "viewer"
        return "own"

    for p in ["top", "viewer"]:
        sub = [r for r in rot if persp(r["question"]) == p]
        dev = [r for r in sub if r["id"] in set(split["Rotation_Direction"]["dev"])]
        ev = [r for r in sub if r["id"] in set(split["Rotation_Direction"]["eval"])]
        # learn sign mapping on dev: does vel_sum>0 mean Clockwise?
        pos_cw = sum(1 for r in dev
                     if (r["data"]["vel_sum"] > 0) == (r["gt"] == "Clockwise"))
        flip = pos_cw < len(dev) / 2

        def acc(ss):
            ok = 0
            for r in ss:
                cw = r["data"]["vel_sum"] > 0
                if flip:
                    cw = not cw
                ok += (cw == (r["gt"] == "Clockwise"))
            return 100 * ok / max(1, len(ss))
        print(f"  persp={p}: dev n={len(dev)} acc={acc(dev):.1f} | "
              f"eval n={len(ev)} acc={acc(ev):.1f} (flip={flip})")

    # ---- Fall: lean_trend sign -> Left/Right; end angle for Lie down/Get up
    fall = [r for r in rows if r["task"] == "Fall_Direction"
            and r["status"] == "success"]
    print(f"\n[Fall] success={len(fall)}/{sum(1 for r in rows if r['task']=='Fall_Direction')}")
    dev = [r for r in fall if r["id"] in set(split["Fall_Direction"]["dev"])]
    ev = [r for r in fall if r["id"] in set(split["Fall_Direction"]["eval"])]

    def is_lr(r):
        return any("Left" in o or "Right" in o for o in r["options"])

    def leftopt(r):
        return [o for o in r["options"] if "Left" in o][0]

    lr = [r for r in fall if is_lr(r)]
    pos_left = sum(1 for r in lr if r["id"] in set(split["Fall_Direction"]["dev"])
                   and (r["data"]["lean_trend"] < 0) == (r["gt"] == leftopt(r)))
    n_dev_lr = sum(1 for r in lr if r["id"] in set(split["Fall_Direction"]["dev"]))
    flip_f = pos_left < n_dev_lr / 2 if n_dev_lr else False

    def acc_f(ss):
        ok = tot = 0
        for r in ss:
            if is_lr(r):
                left = r["data"]["lean_trend"] < 0
                if flip_f:
                    left = not left
                a = leftopt(r) if left else [o for o in r["options"] if "Right" in o][0]
            else:
                a = "Lie down" if r["data"]["end_abs_angle"] > 55 else r["options"][0]
            tot += 1
            ok += (a == r["gt"])
        return 100 * ok / max(1, tot)
    print(f"  dev n={len(dev)} acc={acc_f(dev):.1f} | eval n={len(ev)} acc={acc_f(ev):.1f}")

    for task in ["Rotation_Direction", "Fall_Direction"]:
        tt = [r for r in rows if r["task"] == task]
        b = 100 * np.mean([base[str(r["id"])]["correct"] for r in tt])
        print(f"  baseline({task}) = {b:.1f}")


if __name__ == "__main__":
    main()
