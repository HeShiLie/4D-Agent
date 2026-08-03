"""Generic solver: template-based evidence gathering for tasks without dedicated recipes.

Instead of asking the VLM to generate arbitrary Python code, we provide
pre-built analysis strategies that always produce valid code. The VLM only
needs to select which strategies to apply and how to interpret results.
"""
from __future__ import annotations


def build_generic_code(analysis_spec: dict) -> str:
    """Build valid Python code from analysis_spec strategies.

    The VLM's planner outputs which strategies to use; this function
    generates syntactically-correct code that's guaranteed to execute.
    """
    strategies = analysis_spec.get("required_observations", [])
    entities = analysis_spec.get("entities", [])
    colors = [e for e in entities if e.lower() in ("green", "blue", "red", "yellow", "orange")]

    code_parts = ["def solve(ctx):", "    observations = []", "    measurements = []",
                  "    frames = ctx.get_frames(n=16, scale=0.5)", ""]

    has_strategy = False

    for obs in strategies:
        how = obs.get("how", "").lower() if isinstance(obs, dict) else ""
        what = (obs.get("what", "") if isinstance(obs, dict) else str(obs)).lower()

        if ("track_colored_box" in how or "colored_box" in how) and colors:
            has_strategy = True
            c = colors if colors else ["green", "blue"]
            code_parts.append(f"    # Track colored boxes")
            code_parts.append(f"    track_data = ctx.tracking.track_colored_boxes({c}, max_frames=160, scale=0.5)")
            code_parts.append(f"    for color in {c}:")
            code_parts.append(f"        stats = ctx.tracking.box_series_stats(track_data.get(color, []))")
            code_parts.append(f"        if stats:")
            code_parts.append(f"            measurements.append(Measurement(name=f'{{color}}_hit_ratio', value=stats.get('hit_ratio', 0), unit='ratio', method='box_tracking'))")
            code_parts.append(f"            centers = stats.get('centers')")
            code_parts.append(f"            if centers is not None and len(centers) > 1:")
            code_parts.append(f"                disp = np.linalg.norm(centers[-1] - centers[0])")
            code_parts.append(f"                measurements.append(Measurement(name=f'{{color}}_displacement', value=float(disp), unit='px', method='first_to_last'))")
            code_parts.append("")

        elif "compensate" in how or "ego" in how or "residual" in how:
            has_strategy = True
            c = colors if colors else ["green", "blue"]
            code_parts.append(f"    # Ego-motion compensation")
            code_parts.append(f"    stats = ctx.motion_geometry.compensate_camera_motion(colors={c}, max_frames=160, scale=0.5)")
            code_parts.append(f"    for color in {c}:")
            code_parts.append(f"        cd = stats.get('colors', {{}}).get(color, {{}})")
            code_parts.append(f"        resid = cd.get('resid_center_mag_mean', 0.0)")
            code_parts.append(f"        measurements.append(Measurement(name=f'{{color}}_residual', value=resid, unit='px/frame', method='ego_compensated'))")
            code_parts.append(f"        observations.append(Observation(name=f'{{color}}_motion', value='moving' if resid > 1.0 else 'static', confidence=min(resid/3, 1.0), supporting_frames=[], method='ego_residual'))")
            code_parts.append("")

        elif "pose" in how or "keypoint" in how or "body" in how:
            has_strategy = True
            code_parts.append(f"    # Pose tracking")
            code_parts.append(f"    kp_series = ctx.tracking.track_keypoints(stride=3, max_frames=200, scale=0.5)")
            code_parts.append(f"    if len(kp_series) >= 2:")
            code_parts.append(f"        first_kp = kp_series[0].get('keypoints') if isinstance(kp_series[0], dict) else kp_series[0]")
            code_parts.append(f"        last_kp = kp_series[-1].get('keypoints') if isinstance(kp_series[-1], dict) else kp_series[-1]")
            code_parts.append(f"        if first_kp is not None and last_kp is not None:")
            code_parts.append(f"            first_arr = np.array(first_kp) if not isinstance(first_kp, np.ndarray) else first_kp")
            code_parts.append(f"            last_arr = np.array(last_kp) if not isinstance(last_kp, np.ndarray) else last_kp")
            code_parts.append(f"            if first_arr.ndim >= 2 and last_arr.ndim >= 2:")
            code_parts.append(f"                vert_change = float(np.mean(last_arr[:, 1]) - np.mean(first_arr[:, 1]))")
            code_parts.append(f"                measurements.append(Measurement(name='body_vertical_change', value=vert_change, unit='px', method='keypoint_tracking'))")
            code_parts.append(f"                observations.append(Observation(name='body_direction', value='moving_down' if vert_change > 20 else 'moving_up' if vert_change < -20 else 'stable', confidence=0.7, supporting_frames=[kp_series[0].get('idx',0), kp_series[-1].get('idx',0)] if isinstance(kp_series[0], dict) else [], method='keypoint_vertical'))")
            code_parts.append("")

        elif "optical_flow" in how or "flow" in how or ("motion" in how and "ego" not in how and "compensate" not in how) or "track_points" in how or "光流" in how:
            has_strategy = True
            code_parts.append(f"    # Optical flow analysis")
            code_parts.append(f"    if len(frames) >= 2:")
            code_parts.append(f"        fr1 = frames[0][1]")
            code_parts.append(f"        fr2 = frames[len(frames)//2][1]")
            code_parts.append(f"        prev, cur, valid = ctx.motion_geometry.optical_flow_lk(fr1, fr2)")
            code_parts.append(f"        if prev is not None and cur is not None:")
            code_parts.append(f"            flow = cur[valid] - prev[valid] if valid is not None and np.any(valid) else cur - prev")
            code_parts.append(f"            mean_flow = np.mean(flow, axis=0) if len(flow) > 0 else np.array([0,0])")
            code_parts.append(f"            measurements.append(Measurement(name='mean_flow_x', value=float(mean_flow[0]), unit='px', method='LK_optical_flow'))")
            code_parts.append(f"            measurements.append(Measurement(name='mean_flow_y', value=float(mean_flow[1]), unit='px', method='LK_optical_flow'))")
            code_parts.append(f"            observations.append(Observation(name='dominant_motion', value=f'dx={{mean_flow[0]:.1f}} dy={{mean_flow[1]:.1f}}', confidence=0.7, supporting_frames=[], method='optical_flow'))")
            code_parts.append("")

        elif "yaw" in how or "camera" in how or "heading" in how or "camera_yaw" in how or "偏转" in how or "运动方向" in what:
            has_strategy = True
            code_parts.append(f"    # Camera yaw estimation")
            code_parts.append(f"    yaw_data = ctx.motion_geometry.estimate_camera_yaw(stride=3, max_frames=300, scale=0.5)")
            code_parts.append(f"    if yaw_data:")
            code_parts.append(f"        yaw_vals = list(yaw_data.values())")
            code_parts.append(f"        total_yaw = yaw_vals[-1] if yaw_vals else 0")
            code_parts.append(f"        measurements.append(Measurement(name='total_camera_yaw', value=float(total_yaw), unit='deg', method='feature_matching'))")
            code_parts.append(f"        observations.append(Observation(name='camera_turn', value='left' if total_yaw > 10 else 'right' if total_yaw < -10 else 'straight', confidence=0.8, supporting_frames=[], method='yaw_estimation'))")
            code_parts.append("")

        elif "blob" in how or "hsv" in how or "detect" in how:
            has_strategy = True
            code_parts.append(f"    # Blob / color detection across frames")
            code_parts.append(f"    for idx, fr in frames[:8]:")
            code_parts.append(f"        blobs = ctx.perception.detect_blobs(fr, [((0, 100, 100), (180, 255, 255))], min_area=100)")
            code_parts.append(f"        if blobs:")
            code_parts.append(f"            observations.append(Observation(name=f'blobs_frame_{{idx}}', value=len(blobs), confidence=0.5, supporting_frames=[idx], method='HSV_detection'))")
            code_parts.append("")

    if not has_strategy:
        # Fallback: basic frame difference + optical flow
        code_parts.append(f"    # Fallback: basic motion analysis")
        code_parts.append(f"    if len(frames) >= 4:")
        code_parts.append(f"        fr1 = frames[0][1]")
        code_parts.append(f"        fr2 = frames[len(frames)//2][1]")
        code_parts.append(f"        fr3 = frames[-1][1]")
        code_parts.append(f"        diff_12 = np.mean(cv2.absdiff(fr1, fr2))")
        code_parts.append(f"        diff_23 = np.mean(cv2.absdiff(fr2, fr3))")
        code_parts.append(f"        measurements.append(Measurement(name='motion_first_half', value=float(diff_12), unit='mean_pixel_diff', method='frame_diff'))")
        code_parts.append(f"        measurements.append(Measurement(name='motion_second_half', value=float(diff_23), unit='mean_pixel_diff', method='frame_diff'))")
        code_parts.append(f"        observations.append(Observation(name='motion_trend', value='accelerating' if diff_23 > diff_12 * 1.3 else 'decelerating' if diff_12 > diff_23 * 1.3 else 'steady', confidence=0.5, supporting_frames=[], method='frame_difference'))")
        code_parts.append("")
        # Also do optical flow
        code_parts.append(f"        prev, cur, valid = ctx.motion_geometry.optical_flow_lk(fr1, fr2)")
        code_parts.append(f"        if prev is not None and cur is not None:")
        code_parts.append(f"            flow = cur - prev")
        code_parts.append(f"            if valid is not None and np.any(valid):")
        code_parts.append(f"                flow = flow[valid.flatten()]")
        code_parts.append(f"            mean_flow = np.mean(flow, axis=0) if len(flow) > 0 else np.array([0,0])")
        code_parts.append(f"            measurements.append(Measurement(name='mean_flow_x', value=float(mean_flow[0]), unit='px', method='LK_flow'))")
        code_parts.append(f"            measurements.append(Measurement(name='mean_flow_y', value=float(mean_flow[1]), unit='px', method='LK_flow'))")
        code_parts.append("")

    # Return statement
    code_parts.append(f"    status = 'success' if measurements or observations else 'partial'")
    code_parts.append(f"    return EvidenceBundle(")
    code_parts.append(f"        execution_status=status,")
    code_parts.append(f"        observations=observations,")
    code_parts.append(f"        measurements=measurements,")
    code_parts.append(f"        artifacts=[],")
    code_parts.append(f"        warnings=[],")
    code_parts.append(f"        limitations=[]")
    code_parts.append(f"    )")

    return "\n".join(code_parts)
