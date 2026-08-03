"""Tracking service — track objects, points, keypoints across frames."""
from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .context import SolveContext


LK_PARAMS = dict(winSize=(21, 21), maxLevel=3,
                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))


class TrackingService:
    """Track detected objects or arbitrary points across video frames."""

    def __init__(self, ctx: SolveContext):
        self._ctx = ctx

    def track_colored_boxes(self, colors: list[str],
                            max_frames: int = 200,
                            scale: float = 0.5) -> dict:
        """Track colored-box overlays across the entire video.

        Args:
            colors: list of color names ('green', 'blue').
            max_frames: max frames to process.
            scale: resize factor for processing.

        Returns:
            {color: [(frame_idx, (x,y,w,h) or None), ...], 'info': dict, 'scale': float}
        """
        from agent.tools.ground_track import track_boxes, box_series
        raw = track_boxes(self._ctx.video_path, colors,
                          max_frames=max_frames, scale=scale)
        result = {"info": raw["info"], "scale": raw["scale"]}
        for c in colors:
            result[c] = raw["tracks"][c]
        return result

    def box_series_stats(self, track: list[tuple]) -> dict:
        """Compute trajectory statistics from a box track.

        Args:
            track: [(frame_idx, (x,y,w,h) or None), ...]

        Returns:
            {centers: ndarray(N,2), areas: ndarray(N,), idxs: ndarray(N,),
             hit_ratio: float, n_frames: int}
        """
        from agent.tools.ground_track import box_series
        return box_series(track)

    def track_points(self, frame1: np.ndarray, points: np.ndarray,
                     frame2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Track points from frame1 to frame2 using Lucas-Kanade optical flow.

        Args:
            frame1: first frame (BGR).
            points: np.ndarray of shape (N, 2) — points in frame1.
            frame2: second frame (BGR).

        Returns:
            (tracked_points, valid_mask) — tracked_points shape (N, 2),
            valid_mask shape (N,) bool.
        """
        g1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        pts = points.reshape(-1, 1, 2).astype(np.float32)
        cur, st, _ = cv2.calcOpticalFlowPyrLK(g1, g2, pts, None, **LK_PARAMS)
        st = st.ravel().astype(bool)
        cur = cur.reshape(-1, 2)
        return cur, st

    def track_points_multi(self, start_frame_idx: int, points: np.ndarray,
                           n_forward: int = 30,
                           scale: float = 0.5) -> np.ndarray:
        """Track points forward through multiple frames.

        Args:
            start_frame_idx: frame index to start from.
            points: (N, 2) initial point positions.
            n_forward: number of frames to track forward.
            scale: video read scale.

        Returns:
            trajectory array of shape (n_steps, N, 2). NaN where lost.
        """
        cap = cv2.VideoCapture(self._ctx.video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame_idx)
        ok, fr = cap.read()
        if not ok:
            cap.release()
            return np.full((n_forward, len(points), 2), np.nan)
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)

        prev_gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        pts = points.copy().reshape(-1, 1, 2).astype(np.float32)
        traj = [points.copy()]
        valid = np.ones(len(points), dtype=bool)

        for _ in range(n_forward):
            ok, fr = cap.read()
            if not ok:
                break
            if scale != 1.0:
                fr = cv2.resize(fr, None, fx=scale, fy=scale)
            gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            cur, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pts, None,
                                                   **LK_PARAMS)
            st = st.ravel().astype(bool)
            valid &= st
            new_pts = cur.reshape(-1, 2)
            new_pts[~valid] = np.nan
            traj.append(new_pts.copy())
            pts = cur
            pts[~valid.reshape(-1, 1).repeat(2, axis=1)] = 0
            pts = pts.reshape(-1, 1, 2)
            prev_gray = gray

        cap.release()
        return np.array(traj)

    def track_keypoints(self, stride: int = 2, max_frames: int = 300,
                        scale: float = 0.5, conf: float = 0.35) -> list[dict]:
        """Track the largest person's pose keypoints through the video.

        Returns:
            list of {idx: int, keypoints: np.ndarray(17,3) or None}
        """
        from agent.tools.frames import iter_frames as _iter
        frames = []
        for i, fr in _iter(self._ctx.video_path, max_n=max_frames, stride=stride):
            if scale != 1.0:
                fr = cv2.resize(fr, None, fx=scale, fy=scale)
            frames.append((i, fr))
        return self._ctx.perception.pose_series(frames, conf=conf)
