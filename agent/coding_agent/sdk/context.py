"""SolveContext — the single object passed into generated solve() code."""
from __future__ import annotations

import os
import tempfile

import cv2
import numpy as np

from agent.tools.frames import video_info, uniform_frames, iter_frames


class SolveContext:
    """Context object available as `ctx` inside generated code.

    Provides video frame access and SDK service handles.
    """

    def __init__(self, video_path: str, question: str, options: list[str],
                 artifacts_dir: str | None = None):
        self.video_path = video_path
        self.question = question
        self.options = options
        self.artifacts_dir = artifacts_dir or tempfile.mkdtemp(prefix="vistr_")
        os.makedirs(self.artifacts_dir, exist_ok=True)

        from .perception import PerceptionService
        from .tracking import TrackingService
        from .motion_geometry import MotionGeometryService
        from .visualization import VisualizationService

        self.perception = PerceptionService(self)
        self.tracking = TrackingService(self)
        self.motion_geometry = MotionGeometryService(self)
        self.viz = VisualizationService(self)

    @property
    def info(self) -> dict:
        """Video metadata: {frames, fps, w, h}."""
        return video_info(self.video_path)

    def get_frames(self, n: int = 16, scale: float = 0.5) -> list[tuple[int, np.ndarray]]:
        """Return n uniformly-sampled frames as (frame_idx, bgr_array) pairs."""
        return uniform_frames(self.video_path, n=n, scale=scale)

    def get_frame(self, idx: int, scale: float = 0.5) -> np.ndarray:
        """Read a single frame by index."""
        cap = cv2.VideoCapture(self.video_path)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        cap.release()
        if not ok:
            raise ValueError(f"Cannot read frame {idx}")
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        return fr

    def iter_frames(self, max_n: int = 200, stride: int = 1,
                    scale: float = 0.5):
        """Iterate frames yielding (idx, scaled_bgr). Generator."""
        for i, fr in iter_frames(self.video_path, max_n=max_n, stride=stride):
            if scale != 1.0:
                fr = cv2.resize(fr, None, fx=scale, fy=scale)
            yield i, fr
