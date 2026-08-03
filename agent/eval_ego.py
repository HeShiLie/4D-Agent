#!/usr/bin/env python
"""Ego Motion pipeline: qwen grounds target bearing per sampled frame,
odometry accumulates camera yaw -> final bearing quadrant -> answer.

Run: /opt/conda/envs/python3.10.13/bin/python -u agent/eval_ego.py
(vlm 调用 + cv2；无需 torch，但沿用统一环境)
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.tools import BENCH_DIR, evidence
from agent.tools.ego_odom import odometry_yaw
from agent.tools.qwen_ground import ground_target

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJ_DIR, "outputs", "tool_runs", "ego_motion.jsonl")
HALF_FOV_DEG = 32.0


def parse_target(question):
    m = re.search(r"target object is the ([^.\]]+?)(?:\.|$)", question)
    return m.group(1).strip() if m else "object"


def quadrant(bearing_deg):
    if abs(bearing_deg) <= 90:
        fb = "Front"
    else:
        fb = "Back"
    lr = "right" if bearing_deg > 0 else "left"
    return f"{fb}-{lr}"


def ego_motion(row, odom_cache={}):
    vpath = os.path.join(BENCH_DIR, row["video"])
    target = parse_target(row["direct_prompting"])
    grounds = ground_target(vpath, target, n_samples=8)
    yaw, info = odometry_yaw(vpath)
    n_last = max(yaw) if yaw else 0
    vis = [g for g in grounds if g.get("visible") and g.get("bearing") is not None]
    data = {"target": target, "n_visible": len(vis), "grounds": grounds}
    if not vis or n_last == 0:
        return evidence("ego_motion", "uncertain",
                        f"目标 {target} 未有效定位 ({len(vis)}/8 帧可见)", data)
    g = vis[-1]
    b_deg = g["bearing"] * HALF_FOV_DEG
    yaws = sorted(yaw.items())
    yaw_k = np.interp(g["idx"], [i for i, _ in yaws], [v for _, v in yaws])
    yaw_end = yaws[-1][1]
    final_bearing = b_deg - (yaw_end - yaw_k)
    data.update({"last_seen_idx": g["idx"], "bearing_at_seen": b_deg,
                 "yaw_at_seen": float(yaw_k), "yaw_end": float(yaw_end),
                 "final_bearing": float(final_bearing),
                 "quadrant": quadrant(final_bearing)})
    return evidence(
        "ego_motion", "success",
        f"目标 {target} 最后见于帧{g['idx']}（视方位 {b_deg:+.0f}°），"
        f"其后相机转向 {yaw_end - yaw_k:+.0f}° → 末帧方位 {final_bearing:+.0f}° "
        f"({data['quadrant']})", data)


def _one(row):
    try:
        ev = ego_motion(row)
        pred = ev["data"].get("quadrant") if ev["status"] == "success" else None
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "options": row["options"], "status": ev["status"],
                "pred": pred, "data": ev["data"]}
    except Exception as e:
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "options": row["options"], "status": "failed", "pred": None,
                "data": {"error": str(e)[:200]}}


def main():
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    rows = [r for r in rows if r["task"] == "Ego_Motion"]
    done = set()
    if os.path.exists(CACHE):
        for l in open(CACHE):
            done.add(json.loads(l)["id"])
    todo = [r for r in rows if r["id"] not in done]
    print(f"todo={len(todo)}", flush=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "a") as f, ThreadPoolExecutor(6) as ex:
        for i, res in enumerate(ex.map(_one, todo), 1):
            f.write(json.dumps(res) + "\n")
            f.flush()
            if i % 5 == 0:
                print(f"[{i}/{len(todo)}]", flush=True)

    # report
    split = json.load(open(os.path.join(PROJ_DIR, "configs", "split.json")))
    base = json.load(open(os.path.join(PROJ_DIR, "configs", "baseline_direct.json")))
    rows = [json.loads(l) for l in open(CACHE)]

    def acc(ss):
        ok = 0
        for r in ss:
            a = r["pred"] if r["pred"] in (r["options"] or []) else \
                base[str(r["id"])]["answer"]
            # snap quadrant to nearest option if not exact match
            if a not in r["options"]:
                a = min(r["options"],
                        key=lambda o: (o.split("-")[0] != a.split("-")[0],
                                       o.split("-")[1] != a.split("-")[1])) \
                    if a else r["options"][0]
            ok += (a == r["gt"])
        return 100 * ok / max(1, len(ss))
    for sp, key in [("dev", "dev"), ("eval", "eval")]:
        ss = [r for r in rows if r["id"] in set(split["Ego_Motion"][key])]
        b = 100 * np.mean([base[str(r["id"])]["correct"] for r in ss])
        print(f"[Ego] {sp}: n={len(ss)} tool_acc={acc(ss):.1f} baseline={b:.1f}")


if __name__ == "__main__":
    main()
