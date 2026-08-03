#!/usr/bin/env python
"""Integrated evaluation: per-task best strategy -> answers.

Strategy per task (chosen on dev):
- Relative_Velocity: pure tool (resid compare)
- Rotation_Direction: tool coverage-gated (|vel_sum|>0.8), else fallback
- Fall_Direction: VLM+evidence (from vlm_evidence2) > tool fallback > plan/verify
- Vehicle_Movement: VLM+evidence (from vlm_evidence) — user said stop iterating
- Passage_Feasibility: VLM+evidence (from vlm_evidence)
- Swimming_Race: plan/verify fallback (VLM+evidence hurts)
- Others: plan/verify fallback (best of plan vs verify per dev)
"""
import json
import os
import sys

import numpy as np

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPLIT = json.load(open(f"{PROJ_DIR}/configs/split.json"))
BASE = json.load(open(f"{PROJ_DIR}/configs/baseline_direct.json"))

pv_path = f"{PROJ_DIR}/outputs/plan_verify/qwen3-vl-plus_plan_verify.jsonl"
PV = {r["id"]: r for r in
      (json.loads(l) for l in open(pv_path)) if "error" not in r}


def load_cache(name):
    p = f"{PROJ_DIR}/outputs/tool_runs/{name}"
    if not os.path.exists(p):
        return {}
    return {r["id"]: r for r in (json.loads(l) for l in open(p))}


MOTION = load_cache("driving_motion.jsonl")
POSE = load_cache("pose_motion.jsonl")
VLM_EV1 = load_cache("vlm_evidence.jsonl")
VLM_EV2 = load_cache("vlm_evidence2.jsonl")


def ans_relvel(sid):
    rec = MOTION.get(sid)
    if not rec or rec["status"] == "failed":
        return None
    g = rec["data"]["colors"].get("green", {})
    b = rec["data"]["colors"].get("blue", {})
    if "resid_center_mag_mean" not in g or "resid_center_mag_mean" not in b:
        return None
    return "Green" if g["resid_center_mag_mean"] > b["resid_center_mag_mean"] \
        else "Blue"


def ans_rotation(sid):
    rec = POSE.get(sid)
    if not rec or rec["status"] == "failed":
        return None
    v = rec["data"].get("vel_sum")
    if v is None or abs(v) < 0.8:
        return None
    return "Clockwise" if v < 0 else "Counterclockwise"


def ans_fall_tool(sid):
    rec = POSE.get(sid)
    if not rec or rec["status"] == "failed":
        return None
    d = rec["data"]
    opts = rec.get("options", [])
    lr = [o for o in opts if "Left" in o or "Right" in o]
    if lr:
        left = [o for o in opts if "Left" in o][0]
        right = [o for o in opts if "Right" in o][0]
        return left if d["lean_trend"] < 0 else right
    if "Lie down" in opts:
        return "Lie down" if d["end_abs_angle"] > 55 else \
            [o for o in opts if o != "Lie down"][0]
    return None


def ans_vlm_evidence(sid, cache):
    rec = cache.get(sid)
    if not rec or not rec.get("pred"):
        return None
    return rec["pred"]


def fallback_answer(sample_id, mode):
    r = PV.get(sample_id)
    if r is None:
        return None
    if mode == "plan":
        return r["plan"]["answer"]
    if mode == "verify":
        return r["verify"]["answer"]
    return None


def choose_fallback(task, ids_dev):
    best, best_acc = "plan", -1
    for mode in ["plan", "verify"]:
        ok = sum(1 for i in ids_dev
                 if i in PV and fallback_answer(i, mode) == PV[i]["gt"])
        acc = ok / max(1, len(ids_dev))
        if acc > best_acc:
            best, best_acc = mode, acc
    return best


def get_answer(task, sid, fb_mode):
    if task == "Relative_Velocity":
        a = ans_relvel(sid)
        if a:
            return a, "tool"

    elif task == "Rotation_Direction":
        a = ans_rotation(sid)
        if a:
            return a, "tool"

    elif task == "Fall_Direction":
        a = ans_vlm_evidence(sid, VLM_EV2)
        if a:
            return a, "vlm_ev"
        a = ans_fall_tool(sid)
        if a:
            return a, "tool"

    elif task == "Vehicle_Movement":
        a = ans_vlm_evidence(sid, VLM_EV1)
        if a:
            return a, "vlm_ev"

    elif task == "Passage_Feasibility":
        a = ans_vlm_evidence(sid, VLM_EV1)
        if a:
            return a, "vlm_ev"

    fb = fallback_answer(sid, fb_mode)
    return fb, "fallback"


def main():
    fb = {t: choose_fallback(t, SPLIT[t]["dev"]) for t in SPLIT}
    print("fallback per task (dev-chosen):", fb)
    out = []
    for task in SPLIT:
        for sid in SPLIT[task]["dev"] + SPLIT[task]["eval"]:
            gt = PV[sid]["gt"] if sid in PV else BASE[str(sid)]["gt"]
            ans, src = get_answer(task, sid, fb[task])
            out.append({"id": sid, "task": task, "gt": gt, "pred": ans,
                        "correct": ans == gt, "src": src,
                        "split": "dev" if sid in set(SPLIT[task]["dev"]) else "eval"})
    os.makedirs(f"{PROJ_DIR}/outputs/predictions", exist_ok=True)
    with open(f"{PROJ_DIR}/outputs/predictions/vistr_agent_integrated.jsonl", "w") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n{'task':24s} {'split':5s} {'n':>3s} {'base':>6s} {'ours':>6s} {'src_tool':>8s} {'src_vlm':>8s}")
    tot = {"dev": [0, 0, 0], "eval": [0, 0, 0], "all": [0, 0, 0]}
    for task in sorted(SPLIT, key=lambda t: -len(SPLIT[t]["dev"]) - len(SPLIT[t]["eval"])):
        for sp in ["dev", "eval"]:
            ss = [r for r in out if r["task"] == task and r["split"] == sp]
            if not ss:
                continue
            ours = np.mean([r["correct"] for r in ss])
            base = np.mean([BASE[str(r["id"])]["correct"] for r in ss])
            tn = sum(1 for r in ss if r["src"] == "tool")
            vn = sum(1 for r in ss if r["src"] == "vlm_ev")
            print(f"{task:24s} {sp:5s} {len(ss):3d} {100*base:6.1f} {100*ours:6.1f} {tn:8d} {vn:8d}")
            tot[sp][0] += sum(r["correct"] for r in ss)
            tot[sp][1] += sum(BASE[str(r["id"])]["correct"] for r in ss)
            tot[sp][2] += len(ss)
    for sp in ["dev", "eval"]:
        o, b, n = tot[sp]
        tot["all"][0] += o
        tot["all"][1] += b
        tot["all"][2] += n
        print(f"\n== {sp}: ours={100*o/n:.1f} vs baseline={100*b/n:.1f} (n={n})")
    o, b, n = tot["all"]
    print(f"\n== ALL: ours={100*o/n:.1f} vs baseline={100*b/n:.1f} (n={n})")


if __name__ == "__main__":
    main()
