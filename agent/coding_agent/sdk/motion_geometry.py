"""Motion geometry service — optical flow, ego-motion compensation, camera pose."""
from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .context import SolveContext


class MotionGeometryService:
    """Geometric motion analysis: flow, ego compensation, camera pose estimation."""

    def __init__(self, ctx: SolveContext):
        self._ctx = ctx

    def optical_flow_lk(self, frame1: np.ndarray, frame2: np.ndarray,
                        points: np.ndarray | None = None,
                        max_corners: int = 600) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute sparse LK optical flow between two frames.

        Args:
            frame1, frame2: BGR images (same size).
            points: (N,2) array of points in frame1 to track. If None, auto-detect corners.
            max_corners: Shi-Tomasi corners to detect if points is None.

        Returns:
            (prev_pts, cur_pts, valid_mask) — all shape (N, 2) / (N,) bool.
        """
        g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        if points is None:
            pts = cv2.goodFeaturesToTrack(g1, maxCorners=max_corners,
                                          qualityLevel=0.01, minDistance=12)
            if pts is None or len(pts) < 10:
                return np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0, dtype=bool)
            pts = pts.reshape(-1, 1, 2).astype(np.float32)
        else:
            pts = points.reshape(-1, 1, 2).astype(np.float32)

        from .tracking import LK_PARAMS
        cur, st, _ = cv2.calcOpticalFlowPyrLK(g1, g2, pts, None, **LK_PARAMS)
        st = st.ravel().astype(bool)
        return pts.reshape(-1, 2)[st], cur.reshape(-1, 2)[st], st[st]

    def estimate_global_motion(self, prev_pts: np.ndarray, cur_pts: np.ndarray,
                               exclude_box: tuple | None = None) -> tuple:
        """Fit a partial-affine transform (RANSAC) on background points.

        Args:
            prev_pts: (N, 2) points in previous frame.
            cur_pts: (N, 2) corresponding points in current frame.
            exclude_box: (x, y, w, h) — points inside this box are excluded from fitting.

        Returns:
            (affine_2x3: np.ndarray or None, inlier_mask: np.ndarray bool)
        """
        if exclude_box is not None:
            x, y, w, h = exclude_box
            inside = ((prev_pts[:, 0] >= x) & (prev_pts[:, 0] <= x + w) &
                      (prev_pts[:, 1] >= y) & (prev_pts[:, 1] <= y + h))
            bg_prev = prev_pts[~inside]
            bg_cur = cur_pts[~inside]
        else:
            bg_prev, bg_cur = prev_pts, cur_pts

        if len(bg_prev) < 10:
            return None, np.zeros(len(prev_pts), dtype=bool)

        M, inliers = cv2.estimateAffinePartial2D(
            bg_prev, bg_cur, method=cv2.RANSAC, ransacReprojThreshold=2.5)
        inl = inliers.ravel().astype(bool) if inliers is not None else np.zeros(len(bg_prev), dtype=bool)
        return M, inl

    def compensate_camera_motion(self, colors: list[str],
                                 max_frames: int = 160,
                                 scale: float = 0.5) -> dict:
        """Full ego-motion-compensated residual analysis for colored-box targets.

        Wraps the proven motion.analyze_motion pipeline.

        Args:
            colors: target colors to analyze ('green', 'blue').
            max_frames: frames to process.
            scale: resize factor.

        Returns:
            dict with keys:
                'n_pairs': int — number of valid frame pairs.
                'colors': {color: {resid_center_mag_mean, resid_center_mag_p90,
                                    resid_center_net, epi_mean, epi_p90,
                                    epi_net_signed, loom_rate, n} or {n: int if failed}}
                'status': 'success' | 'uncertain' | 'failed'
        """
        from agent.tools.motion import analyze_motion
        result = analyze_motion(self._ctx.video_path, colors=colors,
                                max_frames=max_frames, scale=scale)
        return result["data"] | {"status": result["status"]}

    def estimate_camera_yaw(self, stride: int = 2, max_frames: int = 400,
                            scale: float = 0.5) -> dict:
        """Cumulative camera yaw estimation from essential matrix decomposition.

        Returns:
            {frame_idx: cumulative_yaw_degrees, ...} where positive = turned right.
        """
        from agent.tools.ego_odom import odometry_yaw
        result = odometry_yaw(self._ctx.video_path, stride=stride,
                              max_frames=max_frames, scale=scale)
        if isinstance(result, tuple):
            return result[0]
        return result

    def compute_residual(self, affine: np.ndarray, prev_pts: np.ndarray,
                         cur_pts: np.ndarray) -> np.ndarray:
        """Compute residual flow after applying an affine transform.

        Args:
            affine: 2x3 affine matrix (from estimate_global_motion).
            prev_pts: (N, 2) source points.
            cur_pts: (N, 2) destination points.

        Returns:
            residual vectors (N, 2) = cur_pts - predicted.
        """
        ones = np.hstack([prev_pts, np.ones((len(prev_pts), 1))])
        predicted = (affine @ ones.T).T
        return cur_pts - predicted
