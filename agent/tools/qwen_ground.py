"""T-GEO-b: VLM target grounder — ask qwen where the named target is in sampled frames.

Returns per sampled frame: visible?, image-x bearing (-1..+1, + = right).
Uses the AMAP gateway (agent/llm). Frames extracted on the fly.
"""
import base64
import json
import re

import cv2
import numpy as np

from .. import llm
from .frames import video_info

PROMPT = """这张图来自一段室内移动相机视频。目标物体是【{target}】。
请回答两个问题：
1. 目标在这张图里可见吗？（visible: yes/no）
2. 若可见，它的中心大致在画面的水平什么位置？给 -1.0（最左）到 +1.0（最右）的一个数。

严格按此格式输出两行：
visible: yes 或 no
bearing: <数值>"""


def ground_target(video_path, target, n_samples=8, max_frames=400):
    info = video_info(video_path)
    total = min(info["frames"], max_frames)
    picks = np.linspace(0, total - 1, n_samples).astype(int)
    cap = cv2.VideoCapture(video_path)
    out = []
    for idx in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, fr = cap.read()
        if not ok:
            continue
        fr = cv2.resize(fr, (640, 360))
        b64 = base64.b64encode(
            cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 70])[1]).decode()
        content = [{"type": "text", "text": PROMPT.format(target=target)},
                   {"type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64," + b64}}]
        try:
            r = llm.chat([{"role": "user", "content": content}],
                         max_tokens=50, temperature=0.0, retries=3)
            txt = r["content"]
            vis = "yes" in txt.lower().split("visible:")[-1][:8].lower()
            m = re.search(r"bearing:\s*(-?\d+\.?\d*)", txt)
            bearing = float(m.group(1)) if m else None
            bearing = max(-1.0, min(1.0, bearing)) if bearing is not None else None
            out.append({"idx": int(idx), "visible": vis, "bearing": bearing})
        except Exception as e:
            out.append({"idx": int(idx), "visible": False, "bearing": None,
                        "error": str(e)[:120]})
    cap.release()
    return out
