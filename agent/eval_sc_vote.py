#!/usr/bin/env python
"""Self-consistency voting: call VLM 3x with temperature on stuck tasks.

Target tasks (no tool advantage): Ego_Motion, Basketball_Shot, Soccer_Shot,
Mikado_Dependency, Billiards_Shot, Golf_Shot, Interaction_Direction, Knot_Type.
Uses 15 frames + CoT prompt, majority vote across 3 calls.
"""
import base64
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import llm
from agent.tools import BENCH_DIR

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ_DIR, "outputs", "tool_runs", "sc_vote.jsonl")

TASKS = ["Ego_Motion", "Basketball_Shot", "Soccer_Shot",
         "Mikado_Dependency", "Billiards_Shot", "Golf_Shot",
         "Interaction_Direction", "Knot_Type"]

PROMPT = """以下是一段视频的均匀抽帧（按时间顺序）。请仔细观察帧间变化，逐步推理后回答问题。

【题目】{question}

请先简短分析（2-3句），然后在最后一行单独输出你的最终答案（只写选项原文之一）。
最终答案："""


def frames_b64(video_path, n=15):
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


def ask_once(row, frames, temp=0.7):
    content = [{"type": "text", "text": PROMPT.format(question=row["direct_prompting"])}]
    for b in frames:
        content.append({"type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64," + b}})
    r = llm.chat([{"role": "user", "content": content}], max_tokens=200,
                 temperature=temp, retries=3)["content"].strip()
    for o in row["options"]:
        if o.lower() in r.lower().split("最终答案")[-1].lower() if "最终答案" in r.lower() else r.lower():
            return o
    for o in row["options"]:
        if o.lower() in r.lower():
            return o
    return r


def _one(row):
    try:
        frames = frames_b64(os.path.join(BENCH_DIR, row["video"]))
        votes = []
        for _ in range(3):
            a = ask_once(row, frames, temp=0.7)
            votes.append(a)
        counter = Counter(votes)
        pred = counter.most_common(1)[0][0]
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "pred": pred, "correct": pred == row["answer"],
                "votes": votes}
    except Exception as e:
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "pred": None, "error": str(e)[:150]}


def main():
    rows_all = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    rows = [r for r in rows_all if r["task"] in TASKS]
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            done.add(json.loads(l)["id"])
    todo = [r for r in rows if r["id"] not in done]
    print(f"sc_vote todo={len(todo)}", flush=True)
    with open(OUT, "a") as f, ThreadPoolExecutor(4) as ex:
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
    for task in TASKS:
        for sp in ["dev", "eval"]:
            ss = [r for r in rows if r["task"] == task
                  and r["id"] in set(split[task][sp])]
            if not ss:
                continue
            acc = 100 * np.mean([r["correct"] for r in ss if r.get("pred")])
            b = 100 * np.mean([base[str(r["id"])]["correct"] for r in ss])
            print(f"[{task}] {sp}: sc3={acc:.1f} vs base={b:.1f} (n={len(ss)})")


if __name__ == "__main__":
    main()
