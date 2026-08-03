#!/usr/bin/env python
"""VLM+evidence experiment: feed tool evidence text to qwen with frames.

Tasks: Vehicle_Movement / Passage_Feasibility / Jenga_Stability / Soccer_Shot.
Compare vs direct baseline, dev-then-eval.
"""
import base64
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import llm
from agent.tools import BENCH_DIR
from agent.tools.passage import analyze_passage

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSAGE_CACHE = os.path.join(PROJ_DIR, "outputs", "tool_runs", "passage.jsonl")
OUT = os.path.join(PROJ_DIR, "outputs", "tool_runs", "vlm_evidence.jsonl")


def load(name):
    p = os.path.join(PROJ_DIR, "outputs", "tool_runs", name)
    return {r["id"]: r for r in (json.loads(l) for l in open(p))}


MOTION = load("driving_motion.jsonl")
JENGA = load("jenga.jsonl")
SOCCER = load("soccer_traj.jsonl")


def evidence_text(task, sid):
    if task == "Vehicle_Movement" and sid in MOTION:
        c = MOTION[sid]["data"]["colors"].get("green", {})
        return (f"工具测量(绿框目标车): ego补偿后残差活动={c.get('resid_center_mag_mean', 0):.2f}px/帧, "
                f"净漂移={c.get('resid_center_net', 0):.2f}px/帧, "
                f"对极几何带符号净偏差={c.get('epi_net_signed', 0):.3f}px/帧, "
                f"looming={c.get('loom_rate', 0):+.3f}。"
                f"参考: 静车这些量接近0; 轻微移动的车通常残差/净偏差明显非零。")
    if task == "Jenga_Stability" and sid in JENGA:
        d = JENGA[sid]["data"]
        return (f"工具测量(积木塔): 塔身倾斜(顶-底中心差)={d.get('tower_lean_px', 0):+.1f}px, "
                f"抽拉接触后塔顶晃动={d.get('wobble_px', 0):.1f}px "
                f"(静稳基准std={d.get('pre_std', 0):.1f}px, 比值={d.get('wobble_ratio', 0):.1f}倍)。"
                f"参考: 倾斜大/晃动远大于基准 → 塔不稳定。")
    if task == "Passage_Feasibility" and sid in PASSAGE:
        d = PASSAGE[sid]["data"]
        return (f"工具测量: 锥桶门宽={d.get('gate_gap_px') or -1:.0f}px(0.5倍尺度), "
                f"车辆最大宽度={d.get('vehicle_max_width_px') or -1:.0f}px, "
                f"门宽/车宽={d.get('margin_ratio') or -1:.2f}。"
                f"参考: 比值<1 必然碰撞; 1~1.3 临界; >1.3 较安全。请结合视频判断。")
    if task == "Soccer_Shot" and sid in SOCCER:
        d = SOCCER[sid]["data"]
        if d.get("status") == "success":
            return (f"工具测量: 球轨迹拟合后是否穿过球门线段: {d.get('hit')}, "
                    f"轨迹与球门线最近距离={d.get('min_dist', 0):.3f}(归一化), "
                    f"球门宽={d.get('goal_width', 0):.3f}。")
    return ""


def frames_b64(video_path, n=10):
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for j in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(j * (total - 1) / (n - 1)))
        ok, fr = cap.read()
        if ok:
            fr = cv2.resize(fr, (640, 360))
            out.append(base64.b64encode(
                cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 65])[1]).decode())
    cap.release()
    return out


def ask(row, ev_text):
    content = [{"type": "text", "text":
                "以下是视频均匀抽帧。另附视觉工具对该视频的测量证据（可能含噪声，请自行权衡）。\n"
                f"【工具证据】{ev_text}\n【题目】{row['direct_prompting']}\n"
                "只输出最终答案（选项原文之一，不要解释）。"}]
    for b in frames_b64(os.path.join(BENCH_DIR, row["video"])):
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + b}})
    r = llm.chat([{"role": "user", "content": content}], max_tokens=30,
                 temperature=0.0, retries=3)["content"].strip().strip("。.")
    for o in row["options"]:
        if o.lower() in r.lower():
            return o, r
    return r, r


def _one(row):
    ev_text = evidence_text(row["task"], row["id"])
    if not ev_text:
        return None
    try:
        a, raw = ask(row, ev_text)
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "pred": a, "correct": a == row["answer"], "raw": raw[:80]}
    except Exception as e:
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "pred": None, "error": str(e)[:150]}


def main():
    global PASSAGE
    # passage evidence first (cv2 only, quick)
    rows_all = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    done_p = set()
    if os.path.exists(PASSAGE_CACHE):
        for l in open(PASSAGE_CACHE):
            done_p.add(json.loads(l)["id"])
    todo_p = [r for r in rows_all
              if r["task"] == "Passage_Feasibility" and r["id"] not in done_p]
    if todo_p:
        with open(PASSAGE_CACHE, "a") as f:
            for r in todo_p:
                ev = analyze_passage(os.path.join(BENCH_DIR, r["video"]))
                f.write(json.dumps({"id": r["id"], "task": r["task"],
                                    "gt": r["answer"], "status": ev["status"],
                                    "data": ev["data"]}) + "\n")
        print(f"passage evidence +{len(todo_p)}", flush=True)
    PASSAGE = load("passage.jsonl")

    tasks = ["Vehicle_Movement", "Passage_Feasibility", "Jenga_Stability",
             "Soccer_Shot"]
    rows = [r for r in rows_all if r["task"] in tasks]
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            done.add(json.loads(l)["id"])
    todo = [r for r in rows if r["id"] not in done]
    print(f"vlm+evidence todo={len(todo)}", flush=True)
    with open(OUT, "a") as f, ThreadPoolExecutor(6) as ex:
        for i, res in enumerate(ex.map(_one, todo), 1):
            if res is None:
                continue
            f.write(json.dumps(res) + "\n")
            f.flush()
            if i % 10 == 0:
                print(f"[{i}/{len(todo)}]", flush=True)

    split = json.load(open(os.path.join(PROJ_DIR, "configs", "split.json")))
    base = json.load(open(os.path.join(PROJ_DIR, "configs", "baseline_direct.json")))
    rows = [json.loads(l) for l in open(OUT)]
    for task in tasks:
        for sp in ["dev", "eval"]:
            ss = [r for r in rows if r["task"] == task
                  and r["id"] in set(split[task][sp])]
            if not ss:
                continue
            acc = 100 * np.mean([r["correct"] for r in ss if r.get("pred")])
            b = 100 * np.mean([base[str(r["id"])]["correct"] for r in ss])
            print(f"[{task}] {sp}: vlm+ev={acc:.1f} vs base={b:.1f} (n={len(ss)})")


if __name__ == "__main__":
    main()
