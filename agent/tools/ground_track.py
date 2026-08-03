"""T-A: ground_and_track — visual-prompt box (green/blue rectangle) detection + tracking.

ViSTR driving tasks overlay thin colored rectangles on targets. Pure HSV + contour
detection is near-oracle; no deep model needed (L0 backend).
"""
import cv2
import numpy as np

from . import evidence
from .frames import iter_frames, video_info

_COLOR_RANGES = {
    "green": [((35, 200, 180), (90, 255, 255))],
    "blue": [((100, 180, 120), (135, 255, 255))],
}


def detect_box(frame, color, min_area=60):
    """Find the largest thin rectangle of the given color. -> bbox (x,y,w,h) or None."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for lo, hi in _COLOR_RANGES[color]:
        mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_score = None, 0
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        # thin rectangle: large perimeter^2/area, aspect within reason
        peri = cv2.arcLength(c, True)
        thin = peri / max(np.sqrt(area), 1)
        score = area * min(thin / 6.0, 1.0)
        if score > best_score:
            best, best_score = (x, y, w, h), score
    return best


def track_boxes(video_path, colors, max_frames=200, scale=0.5):
    """Track colored boxes through the video.

    Returns per-color list of (frame_idx, bbox or None), plus meta.
    """
    info = video_info(video_path)
    tracks = {c: [] for c in colors}
    for i, fr in iter_frames(video_path, max_n=max_frames):
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        for c in colors:
            tracks[c].append((i, detect_box(fr, c)))
    return {"tracks": tracks, "info": info, "scale": scale}


def box_series(track, min_hits_ratio=0.6):
    """-> {centers, areas, idxs, hit_ratio} from a track (drops misses)."""
    pts = [(i, b) for i, b in track if b is not None]
    ratio = len(pts) / max(1, len(track))
    centers = np.array([[b[0] + b[2] / 2, b[1] + b[3] / 2] for _, b in pts]) \
        if pts else np.zeros((0, 2))
    areas = np.array([b[2] * b[3] for _, b in pts]) if pts else np.zeros(0)
    idxs = np.array([i for i, _ in pts]) if pts else np.zeros(0, dtype=int)
    return {"centers": centers, "areas": areas, "idxs": idxs,
            "hit_ratio": ratio, "n_frames": len(track)}


def ground_and_track(video_path, colors=("green",), max_frames=200):
    """Tool entry. Evidence: per-color box trajectories."""
    res = track_boxes(video_path, list(colors), max_frames=max_frames)
    data, ok = {}, True
    for c in colors:
        s = box_series(res["tracks"][c])
        data[c] = {"hit_ratio": round(s["hit_ratio"], 3),
                   "n_hits": len(s["centers"]), "n_frames": s["n_frames"]}
        if s["hit_ratio"] < 0.5:
            ok = False
    status = "success" if ok else "uncertain"
    summary = "; ".join(f"{c} 框检出 {data[c]['n_hits']}/{data[c]['n_frames']} 帧"
                        f"({data[c]['hit_ratio']:.0%})" for c in colors)
    return evidence("ground_and_track", status, summary,
                    {"tracks": {c: res["tracks"][c] for c in colors},
                     "info": res["info"], "scale": res["scale"]})
