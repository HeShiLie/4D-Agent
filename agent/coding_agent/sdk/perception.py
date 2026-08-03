"""Perception service — detect, segment, pose, ground."""
from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .context import SolveContext


class PerceptionService:
    """Detect objects, keypoints, and colored overlays in frames."""

    def __init__(self, ctx: SolveContext):
        self._ctx = ctx
        self._pose_model = None

    def detect_colored_box(self, frame: np.ndarray, color: str) -> tuple | None:
        """Detect a colored rectangle overlay (green/blue). Returns (x,y,w,h) or None.

        Args:
            frame: BGR image (any resolution).
            color: 'green' or 'blue'.
        """
        from agent.tools.ground_track import detect_box
        return detect_box(frame, color)

    def detect_all_colored_boxes(self, frames: list[tuple[int, np.ndarray]],
                                 colors: list[str]) -> dict:
        """Batch detect colored boxes across frames.

        Args:
            frames: list of (frame_idx, bgr_array).
            colors: list of color names ('green', 'blue').

        Returns:
            {color: [(frame_idx, bbox_or_None), ...]}
        """
        from agent.tools.ground_track import detect_box
        result = {c: [] for c in colors}
        for idx, fr in frames:
            for c in colors:
                result[c].append((idx, detect_box(fr, c)))
        return result

    def detect_blobs(self, frame: np.ndarray,
                     hsv_ranges: list[tuple[tuple, tuple]],
                     min_area: int = 60) -> list[dict]:
        """Generic HSV blob detection.

        Args:
            frame: BGR image.
            hsv_ranges: list of ((H_lo, S_lo, V_lo), (H_hi, S_hi, V_hi)) tuples.
            min_area: minimum contour area.

        Returns:
            list of {bbox: (x,y,w,h), area: int, centroid: (cx,cy)}
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = np.zeros(hsv.shape[:2], np.uint8)
        for lo, hi in hsv_ranges:
            mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = []
        for c in cnts:
            area = int(cv2.contourArea(c))
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(c)
            out.append({"bbox": (x, y, w, h), "area": area,
                        "centroid": (x + w // 2, y + h // 2)})
        return sorted(out, key=lambda d: -d["area"])

    def pose(self, frame: np.ndarray, conf: float = 0.35) -> list[dict]:
        """Run YOLOv8n-pose on a single frame.

        Args:
            frame: BGR image.
            conf: detection confidence threshold.

        Returns:
            list of {keypoints: np.ndarray(17,3), bbox: (x,y,w,h), conf: float}
            keypoints columns: [x, y, confidence] for each of 17 COCO keypoints.
        """
        if self._pose_model is None:
            from ultralytics import YOLO
            import os
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.abspath(__file__))))),
                "yolov8n-pose.pt")
            self._pose_model = YOLO(model_path)
            self._pose_model.to("cuda")
        results = self._pose_model(frame, verbose=False, conf=conf)
        out = []
        for r in results:
            if r.keypoints is None:
                continue
            kps = r.keypoints.data.cpu().numpy()
            boxes = r.boxes.xywh.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            for k, b, c in zip(kps, boxes, confs):
                out.append({"keypoints": k, "bbox": tuple(b.tolist()),
                            "conf": float(c)})
        return out

    def pose_series(self, frames: list[tuple[int, np.ndarray]],
                    conf: float = 0.35) -> list[dict]:
        """Run pose detection on a frame sequence, returning the largest person per frame.

        Returns:
            list of {idx: int, keypoints: np.ndarray(17,3) or None}
        """
        out = []
        for idx, fr in frames:
            detections = self.pose(fr, conf=conf)
            if detections:
                best = max(detections, key=lambda d: d["bbox"][2] * d["bbox"][3])
                out.append({"idx": idx, "keypoints": best["keypoints"]})
            else:
                out.append({"idx": idx, "keypoints": None})
        return out
