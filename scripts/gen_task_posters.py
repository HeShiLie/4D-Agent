#!/usr/bin/env python
"""Generate one representative poster frame per task for the taxonomy page.

Picks the middle frame of the first video of each task (deterministic),
writes web/posters/<Task_Name>.jpg.
"""
import json
import os

import cv2

PROJ_DIR = "/mnt/xlab-nas-wm/gaozhe.gz/codes/PlayGround/0731-spatial_temperal_agent"
BENCH_DIR = os.path.join(PROJ_DIR, "data", "benchmarks", "ViSTR-Bench-Public")
OUT_DIR = os.path.join(PROJ_DIR, "web", "posters")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    seen = set()
    for r in rows:
        task = r["task"]  # underscored, e.g. Basketball_Shot
        if task in seen:
            continue
        seen.add(task)
        cap = cv2.VideoCapture(os.path.join(BENCH_DIR, r["video"]))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total // 3))
        ok, fr = cap.read()
        cap.release()
        if not ok:
            print(f"[skip] {task}")
            continue
        fr = cv2.resize(fr, (480, 270))
        out = os.path.join(OUT_DIR, task + ".jpg")
        cv2.imwrite(out, fr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        print(f"[ok] {out}")


if __name__ == "__main__":
    main()
