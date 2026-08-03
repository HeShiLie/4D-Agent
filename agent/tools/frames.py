"""Shared frame extraction (full-rate iter + uniform sample)."""
import cv2


def iter_frames(video_path, max_n=None, stride=1):
    """Yield (idx, frame_bgr) at native rate / stride."""
    cap = cv2.VideoCapture(video_path)
    n = 0
    i = 0
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if i % stride == 0:
            yield i, fr
            n += 1
            if max_n and n >= max_n:
                break
        i += 1
    cap.release()


def video_info(video_path):
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {"frames": total, "fps": fps, "w": w, "h": h}


def uniform_frames(video_path, n=16, scale=1.0):
    """Return list of (idx, frame) uniformly covering the video."""
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    if total <= 0:
        cap.release()
        return out
    for j in range(n):
        idx = round(j * (total - 1) / (n - 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        if ok:
            if scale != 1.0:
                fr = cv2.resize(fr, None, fx=scale, fy=scale)
            out.append((idx, fr))
    cap.release()
    return out
