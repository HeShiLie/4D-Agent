#!/usr/bin/env python
"""Second VLM+evidence batch: Rotation / Fall / Swimming.
Swimming uses new lane-progress evidence; Rotation/Fall reuse pose caches.
"""
import base64
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import llm
from agent.tools import BENCH_DIR
from agent.tools.swim import analyze_swim

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SWIM_CACHE = os.path.join(PROJ_DIR, "outputs", "tool_runs", "swim.jsonl")
OUT = os.path.join(PROJ_DIR, "outputs", "tool_runs", "vlm_evidence2.jsonl")


def load(name):
    p = os.path.join(PROJ_DIR, "outputs", "tool_runs", name)
    return {r["id"]: r for r in (json.loads(l) for l in open(p))}


POSE = load("pose_motion.jsonl")


def swim_lanes(question):
    m = re.search(r"lane (\d+) and lane (\d+)", question)
    return (int(m.group(1)), int(m.group(2))) if m else (3, 7)


def evidence_text(task, row):
    sid = row["id"]
    if task in ("Rotation_Direction", "Fall_Direction") and sid in POSE:
        d = POSE[sid]["data"]
        if task == "Rotation_Direction":
            return (f"工具测量(人体姿态序列): 朝向偏移(鼻-肩中点归一化)范围={d.get('facing_range', 0):.2f}, "
                    f"前半球累计速度={d.get('vel_sum', 0):+.2f}, 净位移={d.get('net_shift', 0):+.2f}。"
                    f"约定: 累计速度为负 = 鼻部向画面左侧移动（顺时针的一种体现），为正 = 向右侧。"
                    f"请结合视频与该量判断旋转方向。")
        return (f"工具测量(人体姿态序列): 倾倒趋势(肩-髋水平错位变化)={d.get('lean_trend', 0):+.3f}, "
                f"起始={d.get('lean_start', 0):+.2f}→末段={d.get('lean_end', 0):+.2f}, "
                f"末段躯干倾角={d.get('end_abs_angle', 0):.0f}°。"
                f"约定: 趋势为负 = 躯干向画面左侧倾斜。")
    if task == "Swimming_Race" and sid in SWIM:
        d = SWIM[sid]["data"]
        lanes = [k for k in d if k.startswith("lane") and k != "lanes" and d[k]]
        parts = []
        for k in lanes:
            parts.append(f"{k}: 平均速度{d[k]['vel']:+.2f}px/帧, 前缘速度{d[k]['vel90']:+.2f}px/帧, 净位移{d[k]['net']:+.0f}px")
        return ("工具测量(泳道运动团块跟踪): " + "; ".join(parts) +
                "。速度为负=向画面左移动。谁的速度绝对值大谁更可能先到终点。请结合视频判断。")
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
                "以下是视频均匀抽帧。另附视觉工具测量证据（可能含噪声，请自行权衡）。\n"
                f"【工具证据】{ev_text}\n【题目】{row['direct_prompting']}\n"
                "只输出最终答案（选项原文之一，不要解释）。"}]
    for b in frames_b64(os.path.join(BENCH_DIR, row["video"])):
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + b}})
    r = llm.chat([{"role": "user", "content": content}], max_tokens=30,
                 temperature=0.0, retries=3)["content"].strip().strip("。.")
    for o in row["options"]:
        if o.lower() in r.lower():
            return o
    return r


def _one(row):
    ev_text = evidence_text(row["task"], row)
    if not ev_text:
        return None
    try:
        a = ask(row, ev_text)
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "pred": a, "correct": a == row["answer"]}
    except Exception as e:
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "pred": None, "error": str(e)[:150]}


def main():
    global SWIM
    # swim evidence first
    rows_all = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    done_s = set()
    if os.path.exists(SWIM_CACHE):
        for l in open(SWIM_CACHE):
            done_s.add(json.loads(l)["id"])
    todo_s = [r for r in rows_all
              if r["task"] == "Swimming_Race" and r["id"] not in done_s]
    if todo_s:
        with open(SWIM_CACHE, "a") as f:
            for r in todo_s:
                lanes = swim_lanes(r["direct_prompting"])
                ev = analyze_swim(os.path.join(BENCH_DIR, r["video"]), lanes=lanes)
                f.write(json.dumps({"id": r["id"], "task": r["task"],
                                    "gt": r["answer"], "options": r["options"],
                                    "status": ev["status"], "data": ev["data"]}) + "\n")
                print(f"[swim {r['id']}]", flush=True)
    SWIM = load("swim.jsonl")

    tasks = ["Rotation_Direction", "Fall_Direction", "Swimming_Race"]
    rows = [r for r in rows_all if r["task"] in tasks]
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            done.add(json.loads(l)["id"])
    todo = [r for r in rows if r["id"] not in done]
    print(f"vlm+evidence2 todo={len(todo)}", flush=True)
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
