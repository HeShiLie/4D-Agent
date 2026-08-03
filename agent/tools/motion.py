"""T-B: analyze_motion — ego-motion-compensated target motion (driving tasks L0).

Per consecutive frame pair:
  - LK-track Shi-Tomasi features over the FULL frame
  - background points (outside inflated target box) fit partial-affine (RANSAC)
    = ego-motion proxy
  - residual flow of points INSIDE the target box = target's own motion
Evidence: residual displacement/activity + box-area looming rate.
No final answer is produced; pipelines decide.
"""
import cv2
import numpy as np

from . import evidence
from .frames import iter_frames, video_info
from .ground_track import detect_box

LK_PARAMS = dict(winSize=(21, 21), maxLevel=3,
                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))


def _inside(pts, b, pad=0):
    x, y, w, h = b
    return ((pts[:, 0] >= x - pad) & (pts[:, 0] <= x + w + pad) &
            (pts[:, 1] >= y - pad) & (pts[:, 1] <= y + h + pad))


def analyze_motion(video_path, colors=("green",), max_frames=160, scale=0.5):
    info = video_info(video_path)
    series = {c: {"residual": [], "resid_center": [], "epi": [], "center": [],
                  "area": [], "idx": []}
              for c in colors}
    prev_gray = prev_pts = None
    prev_boxes = {}
    n_pairs = 0
    for i, fr in iter_frames(video_path, max_n=max_frames):
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        boxes = {c: detect_box(fr, c) for c in colors}
        if prev_gray is not None:
            cur_pts, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray,
                                                      prev_pts, None,
                                                      **LK_PARAMS)
            st = st.ravel().astype(bool)
            if st.sum() >= 30:
                p0 = prev_pts[st].reshape(-1, 2)
                p1 = cur_pts[st].reshape(-1, 2)
                any_box = np.zeros(len(p0), bool)
                for c in colors:
                    b = boxes[c] or prev_boxes.get(c)
                    if b is not None:
                        any_box |= _inside(p0, b, pad=10)
                bg = ~any_box
                if bg.sum() >= 20:
                    M, inl = cv2.estimateAffinePartial2D(
                        p0[bg], p1[bg], method=cv2.RANSAC,
                        ransacReprojThreshold=2.5)
                    if M is not None:
                        ones = np.hstack([p0, np.ones((len(p0), 1))])
                        pred = (M @ ones.T).T
                        resid_all = p1 - pred
                        raw_flow = p1 - p0
                        n_pairs += 1
                        # --- epipolar model from bg points (parallax-safe)
                        F = None
                        if bg.sum() >= 30:
                            try:
                                F, _ = cv2.findFundamentalMat(
                                    p0[bg], p1[bg], cv2.USAC_DEFAULT, 2.0, 0.99)
                            except cv2.error:
                                F = None
                        for c in colors:
                            b = boxes[c] or prev_boxes.get(c)
                            pb = prev_boxes.get(c)
                            if b is None:
                                continue
                            x, y, w, h = b
                            cur_c = np.array([x + w / 2, y + h / 2])
                            # --- local ring reference (same-depth static field)
                            ring_b = (int(x - w * 0.6), int(y - h * 0.6),
                                      int(w * 2.2), int(h * 2.2))
                            ring = _inside(p1, ring_b) & ~_inside(p1, b, pad=4)
                            if ring.sum() >= 5:
                                ref = np.median(raw_flow[ring], axis=0)
                            else:
                                ref = np.median(raw_flow[bg], axis=0)
                            # --- interior residual (textured targets)
                            ins = _inside(p1, b, pad=0)
                            if ins.sum() >= 3:
                                r = np.median(resid_all[ins], axis=0)
                                series[c]["residual"].append(r.tolist())
                            # --- box-center residual (textureless targets)
                            if pb is not None:
                                prev_c = np.array([pb[0] + pb[2] / 2,
                                                   pb[1] + pb[3] / 2])
                                rc = (cur_c - prev_c) - ref
                                series[c]["resid_center"].append(rc.tolist())
                                # --- epipolar distance of box center
                                if F is not None:
                                    l = F @ np.array([prev_c[0], prev_c[1], 1.0])
                                    d = (l @ np.array([cur_c[0], cur_c[1], 1.0])) \
                                        / max(np.hypot(l[0], l[1]), 1e-9)
                                    series[c]["epi"].append(float(d))
                            series[c]["center"].append([x + w / 2, y + h / 2])
                            series[c]["area"].append(w * h)
                            series[c]["idx"].append(i)
        prev_boxes = boxes
        prev_gray = gray
        prev_pts = cv2.goodFeaturesToTrack(gray, maxCorners=600,
                                           qualityLevel=0.01, minDistance=12)
        if prev_pts is None or len(prev_pts) < 40:
            prev_gray = None
            continue

    data, uncertain = {"n_pairs": n_pairs, "colors": {}}, False
    for c in colors:
        R = np.array(series[c]["residual"]) if series[c]["residual"] else np.zeros((0, 2))
        RC = np.array(series[c]["resid_center"]) if series[c]["resid_center"] else np.zeros((0, 2))
        E = np.array(series[c]["epi"]) if series[c]["epi"] else np.zeros(0)
        A = np.array(series[c]["area"])
        if len(RC) < 3:
            uncertain = True
            data["colors"][c] = {"n": len(RC)}
            continue
        mag = np.linalg.norm(R, axis=1) if len(R) else np.zeros(0)
        cmag = np.linalg.norm(RC, axis=1)
        loom = 0.0
        if len(A) >= 4 and (A > 0).all():
            t = np.arange(len(A))
            loom = float(np.polyfit(t, np.log(A), 1)[0])
        data["colors"][c] = {
            "n": len(RC),
            "resid_mag_mean": float(mag.mean()) if len(mag) else 0.0,
            "resid_center_mag_mean": float(cmag.mean()),
            "resid_center_mag_p90": float(np.percentile(cmag, 90)),
            "resid_center_net": float(np.linalg.norm(RC.sum(axis=0)) / len(RC)),
            "epi_mean": float(E.mean()) if len(E) else 0.0,
            "epi_p90": float(np.percentile(E, 90)) if len(E) else 0.0,
            "epi_net_signed": float(abs(E.sum()) / len(E)) if len(E) else 0.0,
            "loom_rate": loom,
        }
    status = "failed" if n_pairs < 5 else ("uncertain" if uncertain else "success")
    parts = []
    for c in colors:
        d = data["colors"].get(c, {})
        if "resid_center_mag_mean" in d:
            parts.append(f"{c}: 局部残差(中心) {d['resid_center_mag_mean']:.2f}px/f "
                         f"(p90 {d['resid_center_mag_p90']:.2f}, net {d['resid_center_net']:.2f}), "
                         f"looming {d['loom_rate']:+.3f}")
    return evidence("analyze_motion", status,
                    "; ".join(parts) or "特征不足，无法估计", data)
