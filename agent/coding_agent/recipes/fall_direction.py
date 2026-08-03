"""Recipe: Fall Direction — detect pose keypoints over time, measure lean trend.

Task pattern: Person falling, determine direction (Left/Right/Lie down).
Key technique: Track shoulder-hip lateral offset over time, compute trend.
"""
import numpy as np


def solve(ctx):
    kp_series = ctx.tracking.track_keypoints(stride=2, max_frames=200, scale=0.5)

    valid = [s for s in kp_series if s["keypoints"] is not None]
    if len(valid) < 5:
        return EvidenceBundle(
            execution_status="failed",
            warnings=["Not enough pose detections"]
        )

    # COCO keypoints: 5=left_shoulder, 6=right_shoulder, 11=left_hip, 12=right_hip
    lean_series = []
    angle_series = []
    for s in valid:
        kp = s["keypoints"]
        ls, rs = kp[5], kp[6]
        lh, rh = kp[11], kp[12]
        if min(ls[2], rs[2], lh[2], rh[2]) < 0.3:
            continue
        shoulder_cx = (ls[0] + rs[0]) / 2
        hip_cx = (lh[0] + rh[0]) / 2
        shoulder_cy = (ls[1] + rs[1]) / 2
        hip_cy = (lh[1] + rh[1]) / 2
        lean = shoulder_cx - hip_cx
        lean_series.append(lean)
        angle = np.degrees(np.arctan2(abs(shoulder_cx - hip_cx),
                                       abs(shoulder_cy - hip_cy)))
        angle_series.append(angle)

    if len(lean_series) < 5:
        return EvidenceBundle(
            execution_status="partial",
            warnings=["Insufficient high-confidence keypoints"]
        )

    lean_arr = np.array(lean_series)
    n = len(lean_arr)
    lean_start = float(np.mean(lean_arr[:max(1, n // 4)]))
    lean_end = float(np.mean(lean_arr[-max(1, n // 4):]))
    lean_trend = float(np.polyfit(np.arange(n), lean_arr, 1)[0])
    end_angle = float(np.mean(angle_series[-max(1, n // 4):]))

    measurements = [
        Measurement(name="lean_trend", value=lean_trend, unit="px/frame", method="shoulder-hip offset regression"),
        Measurement(name="lean_start", value=lean_start, unit="px", method="first-quarter mean"),
        Measurement(name="lean_end", value=lean_end, unit="px", method="last-quarter mean"),
        Measurement(name="end_trunk_angle", value=end_angle, unit="degrees", method="arctan(dx/dy)"),
    ]

    observations = [
        Observation(
            name="lean_direction",
            value="leftward" if lean_trend < 0 else "rightward",
            confidence=min(abs(lean_trend) * 20, 1.0),
            supporting_frames=[valid[0]["idx"], valid[-1]["idx"]],
            method="lean trend sign"
        ),
        Observation(
            name="final_posture",
            value="lying_down" if end_angle > 55 else "tilted",
            confidence=0.8 if end_angle > 55 else 0.6,
            supporting_frames=[valid[-1]["idx"]],
            method="end trunk angle"
        ),
    ]

    art = ctx.viz.plot_timeseries(
        {"lean_offset": lean_series, "trunk_angle": angle_series},
        title="Lean and angle over time"
    )

    return EvidenceBundle(
        execution_status="success",
        observations=observations,
        measurements=measurements,
        artifacts=[art] if art else [],
        limitations=["Image-space lean, not metric"]
    )
