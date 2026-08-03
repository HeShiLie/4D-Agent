"""Action Executor: converts model's JSON plan into SDK calls.

Each action maps to a pre-built, tested code block. No model-generated
Python — all code is deterministic and guaranteed to execute.
"""
from __future__ import annotations

import numpy as np
import cv2

from agent.coding_agent.schemas import EvidenceBundle, Observation, Measurement
from agent.coding_agent.sdk.context import SolveContext


def execute_plan(ctx: SolveContext, plan: dict) -> EvidenceBundle:
    """Execute a structured plan against the SDK.

    Args:
        ctx: SolveContext with video access and SDK services
        plan: dict with "actions" list, each having "action" and "params"

    Returns:
        EvidenceBundle with all collected evidence
    """
    observations = []
    measurements = []
    warnings = []

    actions = plan.get("actions", [])
    if not actions:
        warnings.append("No actions in plan")

    for act in actions:
        name = act.get("action", "")
        params = act.get("params", {})
        try:
            obs, meas, warns = _dispatch(ctx, name, params)
            observations.extend(obs)
            measurements.extend(meas)
            warnings.extend(warns)
        except Exception as e:
            warnings.append(f"Action '{name}' failed: {type(e).__name__}: {e}")

    status = "success" if observations or measurements else "partial"
    return EvidenceBundle(
        execution_status=status,
        observations=observations,
        measurements=measurements,
        artifacts=[],
        warnings=warnings,
        limitations=[],
    )


def _dispatch(ctx, action: str, params: dict):
    """Dispatch one action. Returns (observations, measurements, warnings)."""
    dispatch = {
        "track_colored_boxes": _act_track_boxes,
        "compensate_camera_motion": _act_compensate,
        "estimate_camera_yaw": _act_yaw,
        "track_keypoints": _act_keypoints,
        "optical_flow": _act_optical_flow,
        "detect_blobs": _act_detect_blobs,
        "frame_diff": _act_frame_diff,
        "visual_observation": _act_noop,
    }
    fn = dispatch.get(action)
    if fn is None:
        return [], [], [f"Unknown action: {action}"]
    return fn(ctx, params)


def _act_track_boxes(ctx, params):
    obs, meas, warns = [], [], []
    colors = params.get("colors", ["green", "blue"])
    track = ctx.tracking.track_colored_boxes(colors, max_frames=160, scale=0.5)
    for color in colors:
        series = track.get(color, [])
        stats = ctx.tracking.box_series_stats(series)
        if stats:
            hr = stats.get("hit_ratio", 0)
            meas.append(Measurement(
                name=f"{color}_hit_ratio", value=float(hr),
                unit="ratio", method="box_tracking"))
            centers = stats.get("centers")
            if centers is not None and len(centers) > 1:
                disp = float(np.linalg.norm(centers[-1] - centers[0]))
                meas.append(Measurement(
                    name=f"{color}_displacement", value=disp,
                    unit="px", method="first_to_last"))
                areas = stats.get("areas")
                if areas is not None and len(areas) > 1:
                    loom = float(areas[-1] / max(areas[0], 1) - 1)
                    meas.append(Measurement(
                        name=f"{color}_loom", value=loom,
                        unit="ratio", method="area_change"))
            obs.append(Observation(
                name=f"{color}_tracking",
                value=f"hit_ratio={hr:.2f}, frames={len(series)}",
                confidence=min(hr, 1.0),
                supporting_frames=[],
                method="track_colored_boxes"))
        else:
            warns.append(f"No detections for color '{color}'")
    return obs, meas, warns


def _act_compensate(ctx, params):
    obs, meas, warns = [], [], []
    colors = params.get("colors", ["green", "blue"])
    stats = ctx.motion_geometry.compensate_camera_motion(
        colors=colors, max_frames=160, scale=0.5)
    for color in colors:
        cd = stats.get("colors", {}).get(color, {})
        resid = cd.get("resid_center_mag_mean", 0.0)
        n = cd.get("n", 0)
        meas.append(Measurement(
            name=f"{color}_residual_motion", value=float(resid),
            unit="px/frame", method="ego_compensated"))
        obs.append(Observation(
            name=f"{color}_activity",
            value="moving" if resid > 1.0 else "nearly_static",
            confidence=min(resid / 3.0, 1.0),
            supporting_frames=[],
            method="ego_compensated_LK_residual"))
    n_pairs = stats.get("n_pairs", 0)
    if n_pairs < 5:
        warns.append(f"Few frame pairs analyzed: {n_pairs}")
    return obs, meas, warns


def _act_yaw(ctx, params):
    obs, meas, warns = [], [], []
    yaw_data = ctx.motion_geometry.estimate_camera_yaw(
        stride=3, max_frames=300, scale=0.5)
    if yaw_data:
        vals = list(yaw_data.values())
        total = float(vals[-1]) if vals else 0
        meas.append(Measurement(
            name="total_camera_yaw", value=total,
            unit="deg", method="feature_matching"))
        direction = "left" if total > 10 else "right" if total < -10 else "straight"
        obs.append(Observation(
            name="camera_heading_change",
            value=f"{direction} ({total:.1f}°)",
            confidence=0.8,
            supporting_frames=[],
            method="yaw_estimation"))
    else:
        warns.append("Camera yaw estimation returned no data")
    return obs, meas, warns


def _act_keypoints(ctx, params):
    obs, meas, warns = [], [], []
    kp_series = ctx.tracking.track_keypoints(stride=3, max_frames=200, scale=0.5)
    if len(kp_series) < 2:
        warns.append("Insufficient keypoint detections")
        return obs, meas, warns

    def _get_arr(item):
        kp = item.get("keypoints") if isinstance(item, dict) else item
        if kp is None:
            return None
        arr = np.array(kp) if not isinstance(kp, np.ndarray) else kp
        return arr if arr.ndim >= 2 else None

    first = _get_arr(kp_series[0])
    last = _get_arr(kp_series[-1])
    if first is not None and last is not None:
        vert_change = float(np.mean(last[:, 1]) - np.mean(first[:, 1]))
        horiz_change = float(np.mean(last[:, 0]) - np.mean(first[:, 0]))
        meas.append(Measurement(
            name="body_vertical_change", value=vert_change,
            unit="px", method="keypoint_tracking"))
        meas.append(Measurement(
            name="body_horizontal_change", value=horiz_change,
            unit="px", method="keypoint_tracking"))

        if abs(vert_change) > abs(horiz_change):
            direction = "downward" if vert_change > 20 else "upward" if vert_change < -20 else "stable"
        else:
            direction = "rightward" if horiz_change > 20 else "leftward" if horiz_change < -20 else "stable"
        obs.append(Observation(
            name="body_movement_direction", value=direction,
            confidence=0.7,
            supporting_frames=[],
            method="keypoint_displacement"))

        # Lean analysis (shoulder vs hip)
        if first.shape[0] >= 13:
            l_shoulder, r_shoulder = first[5, :2], first[6, :2]
            l_hip, r_hip = first[11, :2], first[12, :2]
            shoulder_mid_first = (l_shoulder + r_shoulder) / 2
            hip_mid_first = (l_hip + r_hip) / 2

            l_shoulder_l, r_shoulder_l = last[5, :2], last[6, :2]
            l_hip_l, r_hip_l = last[11, :2], last[12, :2]
            shoulder_mid_last = (l_shoulder_l + r_shoulder_l) / 2
            hip_mid_last = (l_hip_l + r_hip_l) / 2

            lean_x = float((shoulder_mid_last[0] - hip_mid_last[0]) -
                           (shoulder_mid_first[0] - hip_mid_first[0]))
            obs.append(Observation(
                name="torso_lean_direction",
                value="rightward" if lean_x > 5 else "leftward" if lean_x < -5 else "neutral",
                confidence=0.8,
                supporting_frames=[],
                method="shoulder_hip_displacement"))
            meas.append(Measurement(
                name="torso_lean_x", value=lean_x,
                unit="px", method="shoulder_hip_delta"))
    return obs, meas, warns


def _act_optical_flow(ctx, params):
    obs, meas, warns = [], [], []
    frames = ctx.get_frames(n=8, scale=0.5)
    if len(frames) < 2:
        warns.append("Too few frames for optical flow")
        return obs, meas, warns

    fr1 = frames[0][1]
    fr2 = frames[len(frames) // 2][1]
    fr3 = frames[-1][1]

    prev, cur, valid = ctx.motion_geometry.optical_flow_lk(fr1, fr2)
    if prev is not None and cur is not None:
        flow = cur - prev
        if valid is not None and np.any(valid):
            flow = flow[valid.flatten()]
        if len(flow) > 0:
            mean_flow = np.mean(flow, axis=0)
            meas.append(Measurement(
                name="mean_flow_x_first_half", value=float(mean_flow[0]),
                unit="px", method="LK_optical_flow"))
            meas.append(Measurement(
                name="mean_flow_y_first_half", value=float(mean_flow[1]),
                unit="px", method="LK_optical_flow"))
            mag = float(np.mean(np.linalg.norm(flow, axis=1)))
            meas.append(Measurement(
                name="mean_flow_magnitude", value=mag,
                unit="px", method="LK_optical_flow"))
            obs.append(Observation(
                name="dominant_motion",
                value=f"dx={mean_flow[0]:.1f} dy={mean_flow[1]:.1f} mag={mag:.1f}",
                confidence=0.7,
                supporting_frames=[frames[0][0], frames[len(frames)//2][0]],
                method="optical_flow"))
    return obs, meas, warns


def _act_detect_blobs(ctx, params):
    obs, meas, warns = [], [], []
    hsv_ranges = params.get("hsv_ranges", [((0, 100, 100), (180, 255, 255))])
    min_area = params.get("min_area", 100)
    frames = ctx.get_frames(n=8, scale=0.5)

    total_blobs = 0
    for idx, fr in frames:
        blobs = ctx.perception.detect_blobs(fr, hsv_ranges, min_area=min_area)
        total_blobs += len(blobs)
        if blobs:
            obs.append(Observation(
                name=f"blobs_frame_{idx}",
                value=f"{len(blobs)} detected, largest area={max(b['area'] for b in blobs):.0f}",
                confidence=0.5,
                supporting_frames=[idx],
                method="HSV_detection"))

    meas.append(Measurement(
        name="total_blob_detections", value=float(total_blobs),
        unit="count", method="HSV_detection"))
    return obs, meas, warns


def _act_frame_diff(ctx, params):
    obs, meas, warns = [], [], []
    frames = ctx.get_frames(n=8, scale=0.5)
    if len(frames) < 3:
        warns.append("Too few frames")
        return obs, meas, warns

    diffs = []
    for i in range(1, len(frames)):
        d = float(np.mean(cv2.absdiff(frames[i-1][1], frames[i][1])))
        diffs.append(d)

    meas.append(Measurement(
        name="mean_frame_diff", value=float(np.mean(diffs)),
        unit="pixel_intensity", method="frame_difference"))
    meas.append(Measurement(
        name="max_frame_diff", value=float(np.max(diffs)),
        unit="pixel_intensity", method="frame_difference"))

    first_half = np.mean(diffs[:len(diffs)//2])
    second_half = np.mean(diffs[len(diffs)//2:])
    trend = ("accelerating" if second_half > first_half * 1.3 else
             "decelerating" if first_half > second_half * 1.3 else "steady")
    obs.append(Observation(
        name="motion_trend", value=trend,
        confidence=0.5,
        supporting_frames=[],
        method="frame_difference_trend"))
    return obs, meas, warns


def _act_noop(ctx, params):
    return [], [], []
