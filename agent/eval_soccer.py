#!/usr/bin/env python
"""Soccer Shot pipeline: qwen grounds ball+goal per sampled frame ->
parabola fit on ball trajectory -> intersect with goal mouth -> answer.
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
from agent.tools.frames import video_info

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(PROJ_DIR, "outputs", "tool_runs", "soccer_traj.jsonl")

PROMPT = """这是一段足球任意球的视频帧。请定位（归一化坐标 0.0-1.0，x 向右、y 向下）：
1. 足球中心（若可见）ball: x, y
2. 球门左门柱与右门柱底部 posts: [x1, y1], [x2, y2]（若球门可见）
严格按格式输出三行：
ball: x, y 或 ball: none
posts: [x1, y1], [x2, y2] 或 posts: none"""


def _parse(txt):
    def xy(pat):
        m = re.search(pat, txt)
        return [float(m.group(1)), float(m.group(2))] if m else None
    ball = xy(r"ball:\s*(\d?\.?\d+)[,\s]+(\d?\.?\d+)")
    posts = re.findall(r"\[(\d?\.?\d+)[,\s]+(\d?\.?\d+)\]", txt)
    posts = [[float(a), float(b)] for a, b in posts] if "posts: none" not in txt else []
    return ball, posts


def ground_ball_goal(video_path, n_samples=10):
    info = video_info(video_path)
    picks = np.linspace(0, info["frames"] - 1, n_samples).astype(int)
    cap = cv2.VideoCapture(video_path)
    out = []
    for idx in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, fr = cap.read()
        if not ok:
            continue
        fr = cv2.resize(fr, (768, 432))
        b64 = base64.b64encode(
            cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 75])[1]).decode()
        content = [{"type": "text", "text": PROMPT},
                   {"type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64," + b64}}]
        try:
            r = llm.chat([{"role": "user", "content": content}],
                         max_tokens=60, temperature=0.0, retries=3)
            ball, posts = _parse(r["content"])
            out.append({"idx": int(idx), "ball": ball, "posts": posts})
        except Exception as e:
            out.append({"idx": int(idx), "ball": None, "posts": [],
                        "error": str(e)[:120]})
    cap.release()
    return out


def fit_and_judge(grounds, min_pts=4):
    pts = [(g["ball"], g["idx"]) for g in grounds if g.get("ball")]
    posts = [g["posts"] for g in grounds if len(g.get("posts", [])) >= 2]
    if len(pts) < min_pts or not posts:
        return {"status": "uncertain", "n_ball": len(pts), "n_posts": len(posts)}
    # ball trajectory in image space: y = a*x^2 + b*x + c (or x = a*y^2+... pick better)
    P = np.array([p[0] for p in pts])
    t = np.array([p[1] for p in pts])
    order = np.argsort(t)
    P, t = P[order], t[order]
    # use time-based model x(t), y(t) with quadratic on y, linear/quadratic on x
    cx = np.polyfit(t, P[:, 0], 2)
    cy = np.polyfit(t, P[:, 1], 2)
    t_future = np.linspace(t[-1], t[-1] + (t[-1] - t[0]), 30)
    traj = np.stack([np.polyval(cx, t_future), np.polyval(cy, t_future)], axis=1)
    # goal mouth segment (median over frames)
    P1 = np.median(np.array([p[0] for p in posts]), axis=0)
    P2 = np.median(np.array([p[1] for p in posts]), axis=0)
    # does trajectory cross segment P1-P2?
    def seg_intersect(a, b, c, d):
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
        return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)
    hit = any(seg_intersect(traj[i], traj[i + 1], P1, P2)
              for i in range(len(traj) - 1))
    # distance-to-line alternative: min distance from traj to segment
    dseg = min(np.linalg.norm(np.cross(P2 - P1, P1 - p)) /
               max(np.linalg.norm(P2 - P1), 1e-9) for p in traj)
    return {"status": "success", "hit": hit, "min_dist": float(dseg),
            "n_ball": len(pts), "n_posts": len(posts),
            "goal_width": float(np.linalg.norm(P2 - P1))}


def _one(row):
    try:
        g = ground_ball_goal(os.path.join(BENCH_DIR, row["video"]))
        j = fit_and_judge(g)
        pred = None
        if j["status"] == "success":
            pred = "Yes" if j["hit"] else "No"
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "status": j["status"], "pred": pred,
                "data": {**j, "grounds": g}}
    except Exception as e:
        return {"id": row["id"], "task": row["task"], "gt": row["answer"],
                "status": "failed", "pred": None, "data": {"error": str(e)[:200]}}


def main():
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    rows = [r for r in rows if r["task"] == "Soccer_Shot"]
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
    split = json.load(open(os.path.join(PROJ_DIR, "configs", "split.json")))
    base = json.load(open(os.path.join(PROJ_DIR, "configs", "baseline_direct.json")))
    rows = [json.loads(l) for l in open(CACHE)]
    for sp in ["dev", "eval"]:
        ss = [r for r in rows if r["id"] in set(split["Soccer_Shot"][sp])]
        ok = 0
        for r in ss:
            a = r["pred"] or base[str(r["id"])]["answer"]
            ok += (a == r["gt"])
        b = 100 * np.mean([base[str(r["id"])]["correct"] for r in ss])
        ncov = sum(1 for r in ss if r["pred"])
        print(f"[Soccer] {sp}: acc={100*ok/len(ss):.1f} baseline={b:.1f} "
              f"(tool cover {ncov}/{len(ss)})")


if __name__ == "__main__":
    main()
