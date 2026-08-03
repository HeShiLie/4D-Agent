"""T-P: analyze_pose_motion — YOLOv8n-pose based human motion attributes.

Runs under the ROCm torch env (/opt/conda/envs/python3.10.13/bin/python).

analyze_rotation: 鼻-肩中点归一化偏移 f(t) 的前半球速度符号 → 旋转方向特征
analyze_fall:     肩-髋水平错位趋势 + 躯干倾角 → 倾倒方向特征
Evidence only; 方向→选项的映射由 pipeline 按 perspective/选项学习。
"""
import cv2
import numpy as np

from . import evidence
from .frames import iter_frames, video_info

_model = None


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO("yolov8n-pose.pt")
        _model.to("cuda")
    return _model


NOSE, L_SH, R_SH, L_HIP, R_HIP = 0, 5, 6, 11, 12


def _pose_series(video_path, stride=2, max_frames=300, scale=1.0, conf=0.35):
    """Per-frame largest-person keypoint summary."""
    model = _get_model()
    out = []
    for i, fr in iter_frames(video_path, max_n=max_frames, stride=stride):
        if scale != 1.0:
            fr = cv2.resize(fr, None, fx=scale, fy=scale)
        res = model.predict(fr, verbose=False, device="cuda")[0]
        if res.keypoints is None or len(res.boxes) == 0:
            out.append({"idx": i, "valid": False})
            continue
        # largest person
        areas = res.boxes.xywh[:, 2] * res.boxes.xywh[:, 3]
        k = int(areas.argmax())
        kp = res.keypoints.xy[k].cpu().numpy()
        kc = res.keypoints.conf[k].cpu().numpy()
        rec = {"idx": i, "valid": True}
        for name, j in [("nose", NOSE), ("l_sh", L_SH), ("r_sh", R_SH),
                        ("l_hip", L_HIP), ("r_hip", R_HIP)]:
            rec[name] = [float(kp[j, 0]), float(kp[j, 1]), float(kc[j])]
        out.append(rec)
    return out


def analyze_rotation(video_path, stride=2):
    series = _pose_series(video_path, stride=stride)
    f, idxs = [], []
    for r in series:
        if not r.get("valid"):
            f.append(np.nan)
            idxs.append(r["idx"])
            continue
        n, ls, rs = r["nose"], r["l_sh"], r["r_sh"]
        if n[2] > 0.35 and ls[2] > 0.35 and rs[2] > 0.35:
            w = abs(ls[0] - rs[0])
            f.append((n[0] - (ls[0] + rs[0]) / 2) / max(w, 5.0))
        else:
            f.append(np.nan)
        idxs.append(r["idx"])
    f = np.array(f)
    valid = ~np.isnan(f)
    n_valid = int(valid.sum())
    data = {"n_frames": len(f), "n_valid": n_valid}
    if n_valid < 6:
        return evidence("analyze_pose_motion", "uncertain",
                        f"姿态有效帧不足({n_valid}/{len(f)})", data)
    # median-filter denoise
    fv = f.copy()
    k = 3
    fv_s = np.array([np.nanmedian(fv[max(0, i - k):i + k + 1])
                     for i in range(len(fv))])
    dv = np.diff(fv_s)
    dv = dv[~np.isnan(dv)]
    # front-hemisphere cumulative velocity + oscillation range
    rng = np.nanmax(fv_s) - np.nanmin(fv_s)
    cum = float(np.sum(dv))
    net = float(fv_s[np.where(valid)[0][-1]] - fv_s[np.where(valid)[0][0]])
    data.update({
        "facing_range": float(rng),
        "vel_sum": cum,                    # 前半球累计速度（带符号）
        "vel_mean": cum / max(len(dv), 1),
        "net_shift": net,
    })
    status = "success" if rng > 0.12 and n_valid >= 8 else "uncertain"
    return evidence(
        "analyze_pose_motion", status,
        f"朝向偏移范围 {rng:.2f}, 累计速度 {cum:+.2f}, 净位移 {net:+.2f} "
        f"(valid {n_valid}/{len(f)})", data)


def analyze_fall(video_path, stride=2):
    series = _pose_series(video_path, stride=stride)
    lean, ang = [], []
    for r in series:
        if not r.get("valid"):
            lean.append(np.nan)
            ang.append(np.nan)
            continue
        ls, rs, lh, rh = r["l_sh"], r["r_sh"], r["l_hip"], r["r_hip"]
        if min(ls[2], rs[2], lh[2], rh[2]) > 0.3:
            shx, shy = (ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2
            hix, hiy = (lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2
            tl = max(abs(shy - hiy), 5.0)
            lean.append((shx - hix) / tl)
            ang.append(float(np.degrees(np.arctan2(shx - hix, -(shy - hiy)))))
        else:
            lean.append(np.nan)
            ang.append(np.nan)
    lean = np.array(lean)
    ang = np.array(ang)
    valid = ~np.isnan(lean)
    n_valid = int(valid.sum())
    data = {"n_frames": len(lean), "n_valid": n_valid}
    if n_valid < 5:
        return evidence("analyze_pose_motion", "uncertain",
                        f"姿态有效帧不足({n_valid}/{len(lean)})", data)
    vi = np.where(valid)[0]
    k = max(2, n_valid // 3)
    start = float(np.nanmean(lean[vi[:k]]))
    end = float(np.nanmean(lean[vi[-k:]]))
    end_ang = float(np.nanmean(np.abs(ang[vi[-k:]])))
    data.update({"lean_start": start, "lean_end": end,
                 "lean_trend": end - start, "end_abs_angle": end_ang})
    return evidence(
        "analyze_pose_motion", "success",
        f"倾倒趋势 {data['lean_trend']:+.3f} (start {start:+.2f}→end {end:+.2f}), "
        f"末段躯干倾角 {end_ang:.0f}°", data)
