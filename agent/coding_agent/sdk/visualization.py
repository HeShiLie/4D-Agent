"""Visualization service — generate inspection artifacts for agent self-check."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .context import SolveContext


class VisualizationService:
    """Generate visual artifacts (PNGs) for inspection by the agent or verifier."""

    def __init__(self, ctx: SolveContext):
        self._ctx = ctx
        self._counter = 0

    def _path(self, name: str) -> str:
        self._counter += 1
        p = os.path.join(self._ctx.artifacts_dir, f"{self._counter:02d}_{name}.png")
        return p

    def contact_sheet(self, frames: list[tuple[int, np.ndarray]],
                      cols: int = 4, title: str = "") -> str:
        """Save a grid of frames as a single PNG.

        Args:
            frames: list of (frame_idx, bgr_array).
            cols: number of columns in the grid.
            title: optional title text (drawn on top).

        Returns:
            Path to saved PNG file.
        """
        if not frames:
            return ""
        h, w = frames[0][1].shape[:2]
        rows_n = (len(frames) + cols - 1) // cols
        canvas = np.zeros((rows_n * (h + 30), cols * w, 3), np.uint8)
        for i, (idx, fr) in enumerate(frames):
            r, c = divmod(i, cols)
            y0 = r * (h + 30) + 30
            canvas[y0:y0 + h, c * w:(c + 1) * w] = fr
            cv2.putText(canvas, f"f{idx}", (c * w + 5, y0 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        if title:
            cv2.putText(canvas, title, (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        path = self._path("contact_sheet")
        cv2.imwrite(path, canvas)
        return path

    def overlay_tracks(self, frames: list[tuple[int, np.ndarray]],
                       tracks: dict[str, list[tuple]],
                       colors_map: dict | None = None) -> str:
        """Draw box trajectories overlaid on frames, save as contact sheet.

        Args:
            frames: list of (frame_idx, bgr_array).
            tracks: {label: [(frame_idx, (x,y,w,h) or None), ...]}.
            colors_map: {label: (B,G,R)}. Defaults to green/blue scheme.

        Returns:
            Path to saved PNG.
        """
        default_colors = {"green": (0, 255, 0), "blue": (255, 100, 0),
                          "red": (0, 0, 255), "yellow": (0, 255, 255)}
        if colors_map is None:
            colors_map = default_colors

        annotated = []
        frame_lookup = {idx: fr.copy() for idx, fr in frames}
        for label, track in tracks.items():
            color = colors_map.get(label, (0, 200, 200))
            for idx, bbox in track:
                if bbox is not None and idx in frame_lookup:
                    x, y, w, h = bbox
                    cv2.rectangle(frame_lookup[idx], (x, y), (x + w, y + h), color, 2)
                    cv2.putText(frame_lookup[idx], label, (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        for idx in sorted(frame_lookup):
            annotated.append((idx, frame_lookup[idx]))
        return self.contact_sheet(annotated[:16], title="Track overlay")

    def plot_timeseries(self, series: dict[str, list[float]],
                        x_label: str = "frame", y_label: str = "",
                        title: str = "") -> str:
        """Line chart of one or more time series. Returns path to PNG.

        Args:
            series: {label: [values...]}.
            x_label: X axis label.
            y_label: Y axis label.
            title: chart title.
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 4))
        for label, vals in series.items():
            ax.plot(vals, label=label, linewidth=1.5)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        if title:
            ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        path = self._path("timeseries")
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return path

    def plot_trajectory(self, points: np.ndarray, labels: list[str] | None = None,
                        title: str = "") -> str:
        """2D scatter/line plot of trajectories. Returns path to PNG.

        Args:
            points: (N, 2) or dict of {label: (N, 2)}.
            labels: point labels (if points is a single array).
            title: chart title.
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(6, 6))
        if isinstance(points, dict):
            for label, pts in points.items():
                pts = np.asarray(pts)
                ax.plot(pts[:, 0], pts[:, 1], "o-", label=label, markersize=3)
        else:
            pts = np.asarray(points)
            ax.plot(pts[:, 0], pts[:, 1], "o-", markersize=3)
        ax.set_aspect("equal")
        ax.invert_yaxis()
        if title:
            ax.set_title(title)
        ax.legend()
        path = self._path("trajectory")
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return path
