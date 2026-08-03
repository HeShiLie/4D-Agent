"""T-PR2: Passage evidence — cone gate geometry + vehicle footprint (L0).

Outputs (no answer): cone count, gate gap px, vehicle width px, margin ratio,
vehicle-gate alignment. VLM consumes these as evidence.
"""
import cv2
import numpy as np

from . import evidence
from .frames import iter_frames, video_info

ORANGE = [((5, 180, 150), (22, 255, 255))]


def _cones(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    m = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in ORANGE:
        m |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if 60 < w * h < 30000 and h > w * 0.9:   # cones: tall-ish
            out.append((x, y, w, h))
    return out


def _moving_blob(prev, cur, cones):
    """Largest frame-diff blob outside cones -> vehicle bbox."""
    d = cv2.absdiff(prev, cur)
    d = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
    _, d = cv2.threshold(d, 28, 255, cv2.THRESH_BINARY)
    d = cv2.dilate(d, np.ones((9, 9), np.uint8))
    for (x, y, w, h) in cones:
        cv2.rectangle(d, (x - 4, y - 4), (x + w + 4, y + h + 4), 0, -1)
    cnts, _ = cv2.findContours(d, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < 3000:
        return None
    return cv2.boundingRect(c)


def analyze_passage(video_path, scale=0.5, max_frames=160):
    info = video_info(video_path)
    prev = None
    cones_hist, veh_hist = [], []
    for i, fr in iter_frames(video_path, max_n=max_frames):
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        cones = _cones(fr)
        if prev is not None:
            vb = _moving_blob(prev, fr, cones)
            if vb is not None:
                veh_hist.append((i, vb))
        if cones:
            cones_hist.append((i, cones))
        prev = fr
    data = {}
    if not cones_hist:
        return evidence("analyze_passage", "failed", "未检测到锥桶", data)
    # gate: closest cone pair at LAST frame with cones
    i_last, cones = cones_hist[-1]
    pts = sorted([(x + w / 2, y + h) for (x, y, w, h) in cones])
    gap = None
    if len(pts) >= 2:
        best = min(((np.hypot(a[0] - b[0], a[1] - b[1]), a, b)
                    for ii, a in enumerate(pts) for b in pts[ii + 1:]),
                   key=lambda t: t[0])
        gap = best[0]
    # vehicle at closest approach (max overlap with gate y-range)
    vw = None
    if veh_hist:
        vw = max(v[1][2] for v in veh_hist)      # max observed width
    data = {
        "n_cones_last": len(cones),
        "gate_gap_px": float(gap) if gap else None,
        "vehicle_max_width_px": float(vw) if vw else None,
        "margin_ratio": (float(gap) / float(vw)) if gap and vw else None,
        "n_vehicle_frames": len(veh_hist),
    }
    status = "success" if gap and vw else "uncertain"
    return evidence(
        "analyze_passage", status,
        f"锥桶 {len(cones)} 个, 门宽 {data['gate_gap_px']:.0f}px, "
        f"车宽 {data['vehicle_max_width_px']:.0f}px, "
        f"余量比 {data['margin_ratio']:.2f}" if status == "success"
        else "锥桶或车辆证据不足", data)
