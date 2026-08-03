"""T-GEO-a: visual odometry — per-pair camera yaw estimation (L0, cv2 only).

Indoor ego-motion clips: accumulate yaw (dominant rotation) via essential matrix.
Output: cumulative yaw series (degrees, + = camera turned right).
"""
import cv2
import numpy as np

from .frames import iter_frames, video_info
from .motion import LK_PARAMS


def odometry_yaw(video_path, stride=2, max_frames=400, scale=0.5):
    """-> {frame_idx: cumulative_yaw_deg}. +yaw = camera rotating right (view moves left)."""
    yaw = {0: 0.0}
    total = 0.0
    prev_gray = prev_pts = None
    prev_i = 0
    for i, fr in iter_frames(video_path, max_n=max_frames, stride=stride):
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            cur, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, g, prev_pts, None,
                                                  **LK_PARAMS)
            st = st.ravel().astype(bool)
            if st.sum() >= 15:
                p0 = prev_pts.reshape(-1, 2)[st]
                p1 = cur.reshape(-1, 2)[st]
                E = None
                try:
                    E, _ = cv2.findEssentialMat(
                        p0, p1, focal=max(g.shape[1], g.shape[0]),
                        pp=(g.shape[1] / 2, g.shape[0] / 2),
                        method=cv2.RANSAC, prob=0.999, threshold=1.5)
                except cv2.error:
                    E = None
                if E is not None and E.shape == (3, 3):
                    _, R, _, _ = cv2.recoverPose(E, p0, p1,
                                                 focal=max(g.shape[1], g.shape[0]),
                                                 pp=(g.shape[1] / 2, g.shape[0] / 2))
                    dyaw = np.degrees(np.arctan2(R[0, 2], R[2, 2]))
                    if abs(dyaw) < 15:      # sanity clamp per pair
                        total += dyaw
            yaw[i] = total
        prev_gray = g
        prev_pts = cv2.goodFeaturesToTrack(g, maxCorners=600, qualityLevel=0.01,
                                           minDistance=12)
        prev_i = i
    return yaw, video_info(video_path)
