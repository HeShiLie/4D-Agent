#!/usr/bin/env python
"""Extract K uniform frames from benchmark videos -> one labeled montage per case.

Token-efficient case review: 1 case = 1 montage image (2x2 grid of 4 frames).

Usage:
  /opt/conda/bin/python scripts/extract_case_frames.py --n_per_task 5
"""
import argparse
import json
import os
from collections import defaultdict

import cv2
import numpy as np

PROJ_DIR = "/mnt/xlab-nas-wm/gaozhe.gz/codes/PlayGround/0731-spatial_temperal_agent"
BENCH_DIR = os.path.join(PROJ_DIR, "data", "benchmarks", "ViSTR-Bench-Public")
REVIEW_DIR = os.path.join(PROJ_DIR, "docs", "notes", "analyses",
                          "2026-08-01_case_review")
FRAMES_DIR = os.path.join(REVIEW_DIR, "frames")

FONT = cv2.FONT_HERSHEY_SIMPLEX


def montage(video_path, k=4, tw=640, th=360):
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    if total <= 0:
        cap.release()
        return None, (0, 0, 0, 0)
    idxs = np.linspace(0, total - 1, k).astype(int)
    tiles = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, fr = cap.read()
        if not ok:
            fr = np.zeros((th, tw, 3), np.uint8)
        fr = cv2.resize(fr, (tw, th))
        label = f"f{i}/{total}  t={i / fps:.1f}s"
        cv2.rectangle(fr, (0, 0), (200, 24), (0, 0, 0), -1)
        cv2.putText(fr, label, (4, 17), FONT, 0.55, (0, 255, 255), 1)
        tiles.append(fr)
    cap.release()
    top = np.hstack(tiles[:2])
    bot = np.hstack(tiles[2:]) if len(tiles) > 2 else np.zeros_like(top)
    grid = np.vstack([top, bot])
    return grid, (total, fps, round(total / fps, 2), fr.shape[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n_per_task", type=int, default=5)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    os.makedirs(FRAMES_DIR, exist_ok=True)
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    rng = np.random.default_rng(args.seed)

    # stratified: per task, cover both answer classes + diverse sources
    by_task = defaultdict(list)
    for r in rows:
        by_task[r["task"]].append(r)

    worklist = []
    for task in sorted(by_task):
        pool = by_task[task]
        # group by answer, round-robin across answers, prefer diverse datasets
        by_ans = defaultdict(list)
        for r in pool:
            by_ans[r["answer"]].append(r)
        picked, seen_ds = [], set()
        order = sorted(by_ans, key=lambda a: -len(by_ans[a]))
        while len(picked) < min(args.n_per_task, len(pool)):
            progressed = False
            for a in order:
                cands = [r for r in by_ans[a] if r not in picked]
                if not cands:
                    continue
                unseen = [r for r in cands if r["dataset"] not in seen_ds]
                r = unseen[0] if unseen else cands[int(rng.integers(len(cands)))]
                picked.append(r)
                seen_ds.add(r["dataset"])
                progressed = True
                if len(picked) >= min(args.n_per_task, len(pool)):
                    break
            if not progressed:
                break
        worklist.extend(picked)

    manifest = []
    for r in worklist:
        vrel = r["video"]
        vpath = os.path.join(BENCH_DIR, vrel)
        grid, meta = montage(vpath)
        if grid is None:
            print(f"[skip] unreadable: {vrel}")
            continue
        fname = f"{r['task']}_id{r['id']:04d}.jpg"
        cv2.imwrite(os.path.join(FRAMES_DIR, fname), grid,
                    [cv2.IMWRITE_JPEG_QUALITY, 82])
        manifest.append({
            "id": r["id"], "task": r["task"], "dimension": r["dimension"],
            "dataset": r["dataset"], "video": vrel,
            "question": r["direct_prompting"], "options": r["options"],
            "gt": r["answer"], "montage": f"frames/{fname}",
            "n_frames": meta[0], "fps": round(meta[1], 1), "dur_s": meta[2],
        })
        print(f"[ok] {fname}  ({meta[0]}f {meta[2]}s)")

    with open(os.path.join(REVIEW_DIR, "worklist.json"), "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(f"\nworklist: {len(manifest)} cases -> {REVIEW_DIR}/worklist.json")


if __name__ == "__main__":
    main()
