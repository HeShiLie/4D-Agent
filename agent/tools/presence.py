"""T-B2: presence check — is the boxed target still at its original spot later?

Robust Vehicle-Movement signal: crop target content at t0; at later frame k,
search a neighborhood around the affine-predicted static position for the best
template match (NCC). Parallax slack is absorbed by the search window.
  presence 高 → 目标没动过（No）
  presence 低 → 目标已离开原位（Yes）
"""
import cv2
import numpy as np

from . import evidence
from .frames import iter_frames, video_info
from .ground_track import detect_box
from .motion import LK_PARAMS


def _lk_bg(p0_gray, p1_gray, pts):
    cur, st, _ = cv2.calcOpticalFlowPyrLK(p0_gray, p1_gray, pts, None, **LK_PARAMS)
    st = st.ravel().astype(bool)
    return cur.reshape(-1, 2), st


def analyze_presence(video_path, scale=0.5, max_frames=160, inner=0.7):
    info = video_info(video_path)
    frames = {}   # idx -> (gray, box)
    for i, fr in iter_frames(video_path, max_n=max_frames):
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        b = detect_box(fr, "green")
        if b is not None:
            frames[i] = (g, b)
    idxs = sorted(frames)
    if len(idxs) < 6:
        return evidence("analyze_presence", "failed",
                        f"绿框有效帧不足({len(idxs)})", {})
    picks = [idxs[0], idxs[len(idxs) // 3], idxs[2 * len(idxs) // 3], idxs[-1]]
    pairs = [(picks[0], picks[2]), (picks[0], picks[3]),
             (picks[1], picks[3]), (picks[0], picks[1])]
    scores = []
    for t0, tk in pairs:
        g0, b0 = frames[t0]
        gk, bk = frames[tk]
        # bg affine t0 -> tk via LK on features outside box
        mask = np.full(g0.shape, 255, np.uint8)
        x, y, w, h = b0
        cv2.rectangle(mask, (x - 8, y - 8), (x + w + 8, y + h + 8), 0, -1)
        pts = cv2.goodFeaturesToTrack(g0, maxCorners=500, qualityLevel=0.01,
                                      minDistance=12, mask=mask)
        if pts is None or len(pts) < 30:
            continue
        p1, st = _lk_bg(g0, gk, pts)
        p0 = pts.reshape(-1, 2)[st]
        p1 = p1[st]
        if len(p0) < 20:
            continue
        try:
            M, inl = cv2.estimateAffinePartial2D(p0, p1, method=cv2.RANSAC,
                                                 ransacReprojThreshold=2.5)
        except cv2.error:
            continue
        if M is None:
            continue
        c0 = np.array([x + w / 2, y + h / 2, 1.0])
        ck = M @ c0                      # static-predicted center in frame k
        # inner template
        iw, ih = int(w * inner / 2), int(h * inner / 2)
        tpl = g0[int(c0[1]) - ih:int(c0[1]) + ih,
                 int(c0[0]) - iw:int(c0[0]) + iw]
        if tpl.size == 0 or tpl.shape[0] < 8 or tpl.shape[1] < 8:
            continue
        # search window around ck (parallax slack)
        R = int(max(w, h) * 0.9) + 15
        x0, y0 = int(ck[0]), int(ck[1])
        xa, xb = max(0, x0 - R - iw), min(gk.shape[1], x0 + R + iw)
        ya, yb = max(0, y0 - R - ih), min(gk.shape[0], y0 + R + ih)
        win = gk[ya:yb, xa:xb]
        if win.shape[0] <= tpl.shape[0] or win.shape[1] <= tpl.shape[1]:
            continue
        res = cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED)
        scores.append(float(res.max()))
    scores = np.array(scores)
    if not len(scores):
        return evidence("analyze_presence", "failed", "配准失败", {})
    data = {"presence_median": float(np.median(scores)),
            "presence_min": float(scores.min()),
            "presence_max": float(scores.max()),
            "n_pairs": len(scores)}
    status = "success" if len(scores) >= 2 else "uncertain"
    return evidence(
        "analyze_presence", status,
        f"原位保持度 presence={data['presence_median']:.2f} "
        f"(min {data['presence_min']:.2f}, {len(scores)} 对帧)", data)
