"""T-PR: analyze_physical_relations — Jenga tower structure + pull dynamics (L0).

Features (no answer output):
  n_layers, target_row_from_top, blocks_above_target (x-span overlap),
  tower_lean, target_protrusion, wobble (tower-top shift during pull)
"""
import cv2
import numpy as np

from . import evidence
from .frames import iter_frames

RED = [((0, 120, 90), (12, 255, 255)), ((168, 120, 90), (180, 255, 255))]
BLUE = [((95, 90, 60), (130, 255, 200))]
SKIN = [((0, 30, 60), (25, 200, 255))]


def _mask(hsv, ranges):
    m = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in ranges:
        m |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    return m


def _blocks(frame):
    """-> list of block components {x,y,w,h,color,cx,cy}."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    out = []
    for color, rng in [("red", RED), ("blue", BLUE)]:
        m = _mask(hsv, rng)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 3), np.uint8))
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            if w * h < 150 or w < 2 * h:   # blocks are long & flat
                continue
            out.append({"x": x, "y": y, "w": w, "h": h, "color": color,
                        "cx": x + w / 2, "cy": y + h / 2})
    return out


def _hand(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = _mask(hsv, SKIN)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < 800:
        return None
    M = cv2.moments(c)
    if M["m00"] == 0:
        return None
    return (M["m10"] / M["m00"], M["m01"] / M["m00"])


def _tower_top(blocks):
    if not blocks:
        return None
    ys = [b["y"] for b in blocks]
    top = [b for b in blocks if b["y"] <= min(ys) + 12]
    if not top:
        return None
    return float(np.mean([b["cx"] for b in top])), min(ys)


def _tower_mask(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = _mask(hsv, RED) | _mask(hsv, BLUE)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    return m


def _tower_stats(frame):
    """-> (centroid_x, top_x, top_y, bbox) of the tower union mask."""
    m = _tower_mask(frame)
    ys, xs = np.nonzero(m)
    if len(xs) < 200:
        return None
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    top_band = ys < y0 + (y1 - y0) * 0.2
    top_x = float(xs[top_band].mean()) if top_band.sum() else float(xs.mean())
    bot_band = ys > y1 - (y1 - y0) * 0.2
    bot_x = float(xs[bot_band].mean()) if bot_band.sum() else float(xs.mean())
    return float(xs.mean()), top_x, float(y0), bot_x, (x0, y0, x1, y1)


def analyze_jenga(video_path, max_frames=120, scale=0.75):
    stats = {}
    hands = {}
    for i, fr in iter_frames(video_path, max_n=max_frames):
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        s = _tower_stats(fr)
        if s is not None:
            stats[i] = s
        hands[i] = _hand(fr)
    if len(stats) < 10:
        return evidence("analyze_physical_relations", "failed",
                        f"塔体有效帧不足({len(stats)})", {})
    idxs = sorted(stats)
    # contact frame: hand nearest to tower bbox
    contact_i, best = None, 1e18
    for i in idxs:
        h = hands.get(i)
        if h is None:
            continue
        x0, y0, x1, y1 = stats[i][4]
        d = np.hypot(max(x0 - h[0], 0, h[0] - x1), max(y0 - h[1], 0, h[1] - y1))
        if d < best:
            best, contact_i = d, i
    if contact_i is None:
        contact_i = idxs[len(idxs) // 2]
    cx = np.array([stats[i][1] for i in idxs])      # top-band centroid x
    # lean: top vs bottom band center at first frame
    s0 = stats[idxs[0]]
    lean = s0[1] - s0[3]
    # wobble: top x drift-corrected fluctuation after contact
    t = np.arange(len(idxs))
    A = np.vstack([t, np.ones_like(t)]).T
    coef, *_ = np.linalg.lstsq(A, cx, rcond=None)
    resid = cx - (A @ coef)
    after = [k for k, i in enumerate(idxs) if i >= contact_i]
    before = [k for k, i in enumerate(idxs) if i < contact_i]
    wobble = float(np.abs(resid[after]).max()) if after else 0.0
    pre_std = float(np.std(resid[before])) if len(before) > 3 else 1.0
    data = {
        "n_frames": len(idxs), "contact_frame": contact_i,
        "tower_lean_px": float(lean),
        "wobble_px": wobble, "wobble_ratio": wobble / max(pre_std, 0.5),
        "pre_std": pre_std,
    }
    return evidence(
        "analyze_physical_relations", "success",
        f"塔身倾斜 {lean:+.1f}px, 接触后晃动 {wobble:.1f}px "
        f"(baseline std {pre_std:.1f}, 比值 {data['wobble_ratio']:.1f}x)", data)
