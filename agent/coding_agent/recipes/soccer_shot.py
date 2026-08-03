"""Recipe: Soccer Shot — track ball motion, check if trajectory crosses goal area.

Task pattern: Free kick video, determine if ball enters the goal.
Key technique: Frame-diff to find fast-moving small ball, fit trajectory, check goal intersection.
"""
import numpy as np


def solve(ctx):
    frames = ctx.get_frames(n=20, scale=0.5)

    # Track moving objects via frame differencing
    ball_candidates = []
    for i in range(1, len(frames)):
        idx_prev, fr_prev = frames[i-1]
        idx_cur, fr_cur = frames[i]
        diff = cv2.absdiff(fr_prev, fr_cur)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 35, 255, cv2.THRESH_BINARY)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Ball: small, roughly circular blob
        for c in cnts:
            area = cv2.contourArea(c)
            if 50 < area < 3000:
                x, y, w, h = cv2.boundingRect(c)
                aspect = w / max(h, 1)
                if 0.5 < aspect < 2.0:
                    cx, cy = x + w//2, y + h//2
                    ball_candidates.append((idx_cur, cx, cy, area))

    if len(ball_candidates) < 3:
        return EvidenceBundle(
            execution_status="partial",
            warnings=["Insufficient ball detections for trajectory fitting"],
            observations=[Observation(
                name="ball_detections", value=len(ball_candidates),
                confidence=0.3, supporting_frames=[], method="frame-diff blob detection"
            )]
        )

    # Cluster ball positions (simple: take the most consistent trajectory)
    pts = np.array([(c[1], c[2]) for c in ball_candidates])
    t = np.array([c[0] for c in ball_candidates])

    # Fit quadratic trajectory: x(t), y(t)
    try:
        cx = np.polyfit(t, pts[:, 0], 2)
        cy = np.polyfit(t, pts[:, 1], 2)
    except Exception:
        return EvidenceBundle(
            execution_status="partial",
            warnings=["Trajectory fitting failed"]
        )

    # Extrapolate forward
    t_ext = np.linspace(t[-1], t[-1] + (t[-1] - t[0]) * 0.5, 20)
    traj_x = np.polyval(cx, t_ext)
    traj_y = np.polyval(cy, t_ext)

    # Goal detection: look for goal area (typically white/net structure in upper portion)
    # Heuristic: check if trajectory moves toward upper portion of frame
    h_frame = frames[0][1].shape[0]
    w_frame = frames[0][1].shape[1]
    enters_upper = np.any(traj_y < h_frame * 0.3)
    trajectory_rising = cy[0] < 0  # negative quadratic means ball goes up then comes down

    # Movement direction
    dx = float(pts[-1, 0] - pts[0, 0])
    dy = float(pts[-1, 1] - pts[0, 1])

    measurements = [
        Measurement(name="ball_detections", value=float(len(ball_candidates)), unit="count", method="frame-diff"),
        Measurement(name="trajectory_dx", value=dx, unit="px", method="first-to-last displacement"),
        Measurement(name="trajectory_dy", value=dy, unit="px", method="first-to-last displacement"),
    ]

    observations = [
        Observation(
            name="ball_trajectory_direction",
            value=f"moving {'up' if dy < 0 else 'down'} and {'right' if dx > 0 else 'left'}",
            confidence=0.6,
            supporting_frames=[int(ball_candidates[0][0]), int(ball_candidates[-1][0])],
            method="trajectory endpoint comparison"
        ),
        Observation(
            name="trajectory_curvature",
            value="arching" if abs(cx[0]) > 0.001 or abs(cy[0]) > 0.001 else "linear",
            confidence=0.5,
            supporting_frames=[],
            method="quadratic coefficient magnitude"
        ),
    ]

    art = ctx.viz.plot_trajectory(
        {"ball": pts, "extrapolated": np.column_stack([traj_x, traj_y])},
        title="Ball trajectory"
    )

    return EvidenceBundle(
        execution_status="success",
        observations=observations,
        measurements=measurements,
        artifacts=[art] if art else [],
        warnings=["Ball detection may include false positives"],
        limitations=["No explicit goal detection; trajectory analysis only"]
    )
