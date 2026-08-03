"""T-SW: Swimming lane progress evidence (L0).

Side-view pool: 检测泳道带（水线/泳池蓝） → 逐带运动团块前缘 x 进度 → 两泳道对比。
Evidence only (progress velocity per lane + who leads at the end).
"""
import cv2
import numpy as np

from . import evidence
from .frames import iter_frames, video_info


def analyze_swim(video_path, lanes=(3, 7), scale=0.5, max_frames=200):
    info = video_info(video_path)
    prev = None
    band = None
    prog = {l: [] for l in lanes}       # per lane: leading-edge x over time
    for i, fr in iter_frames(video_path, max_n=max_frames):
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        if band is None:
            # pool = strongest horizontal edge region: 上下水面边界粗定为中部 15%~85%
            h = g.shape[0]
            band = (int(h * 0.15), int(h * 0.85))
        if prev is not None:
            d = cv2.absdiff(g, prev)
            _, d = cv2.threshold(d, 30, 255, cv2.THRESH_BINARY)
            d = cv2.dilate(d, np.ones((7, 7), np.uint8))
            y0, y1 = band
            for lane, frac in [(l, (l - 0.5) / 8.0) for l in lanes]:
                ly0 = y0 + int((y1 - y0) * frac - (y1 - y0) / 16)
                ly1 = y0 + int((y1 - y0) * frac + (y1 - y0) / 16)
                strip = d[max(0, ly0):min(d.shape[0], ly1), :]
                xs = np.nonzero(strip)[1]
                if len(xs) > 30:
                    prog[lane].append((i, float(xs.mean()),
                                       float(np.percentile(xs, 90)),
                                       float(np.percentile(xs, 10))))
        prev = g
    data = {"lanes": list(lanes)}
    v = {}
    for l in lanes:
        pts = prog[l]
        if len(pts) < 5:
            data[f"lane{l}"] = None
            continue
        t = np.arange(len(pts))
        mean_x = np.array([p[1] for p in pts])
        vel = float(np.polyfit(t, mean_x, 1)[0])
        lead90 = np.array([p[2] for p in pts])
        vel90 = float(np.polyfit(t, lead90, 1)[0])
        v[l] = (vel, vel90, mean_x[-1] - mean_x[0])
        data[f"lane{l}"] = {"vel": vel, "vel90": vel90,
                            "net": float(mean_x[-1] - mean_x[0])}
    ok = all(data.get(f"lane{l}") for l in lanes)
    status = "success" if ok else "uncertain"
    parts = []
    for l in lanes:
        d = data.get(f"lane{l}")
        if d:
            parts.append(f"lane{l}: 速度 {d['vel']:+.2f}px/f "
                         f"(前缘 {d['vel90']:+.2f}), 净进 {d['net']:+.0f}px")
    return evidence("analyze_swim", status, "; ".join(parts) or "泳道证据不足",
                    data)
