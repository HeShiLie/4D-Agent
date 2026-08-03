"""Recipe: Relative Velocity — compare residual motion of two colored-box targets.

Task pattern: Two cars marked with green/blue boxes in a driving video.
Key technique: Ego-motion compensation via background RANSAC affine, then compare residuals.
"""
import numpy as np


def solve(ctx):
    stats = ctx.motion_geometry.compensate_camera_motion(
        colors=["green", "blue"], max_frames=160, scale=0.5)

    observations = []
    measurements = []

    for color in ["green", "blue"]:
        color_data = stats.get("colors", {}).get(color, {})
        resid = color_data.get("resid_center_mag_mean", 0.0)
        n = color_data.get("n", 0)
        measurements.append(Measurement(
            name=f"{color}_residual_motion",
            value=resid,
            unit="px/frame",
            method="compensate_camera_motion"
        ))
        observations.append(Observation(
            name=f"{color}_car_activity",
            value="moving" if resid > 1.0 else "nearly_static",
            confidence=min(resid / 3.0, 1.0),
            supporting_frames=[],
            method="ego-compensated LK residual"
        ))

    green_r = next((m.value for m in measurements if "green" in m.name), 0)
    blue_r = next((m.value for m in measurements if "blue" in m.name), 0)
    observations.append(Observation(
        name="relative_comparison",
        value=f"green={green_r:.2f} vs blue={blue_r:.2f} px/frame; "
              f"{'green' if green_r > blue_r else 'blue'} has more motion",
        confidence=0.9 if abs(green_r - blue_r) > 0.5 else 0.5,
        supporting_frames=[],
        method="direct comparison of residual magnitudes"
    ))

    return EvidenceBundle(
        execution_status="success" if stats.get("n_pairs", 0) >= 5 else "partial",
        observations=observations,
        measurements=measurements,
        artifacts=[],
        warnings=[] if stats.get("n_pairs", 0) >= 10 else ["Few frame pairs analyzed"],
        limitations=["Assumes colored boxes are visible and trackable"]
    )
