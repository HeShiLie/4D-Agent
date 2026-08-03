"""Step 2: Code Generator — generates solve(ctx) -> EvidenceBundle."""

CODEGEN_PROMPT = """根据分析规格，写一个简短的 `solve(ctx)` 函数来收集视频分析证据。

## 分析规格
{analysis_spec}

## SDK（ctx 提供的方法）

帧: ctx.get_frames(n=16, scale=0.5) -> [(idx, bgr)]; ctx.info -> {{frames, fps, w, h}}
检测: ctx.perception.detect_colored_box(frame, color) -> (x,y,w,h)|None
      ctx.perception.detect_blobs(frame, hsv_ranges, min_area=60) -> [{{bbox, area, centroid}}]
      ctx.perception.pose(frame) -> [{{keypoints: ndarray(17,3), bbox, conf}}]
跟踪: ctx.tracking.track_colored_boxes(colors, max_frames=200, scale=0.5) -> {{color: [(idx, bbox|None)]}}
      ctx.tracking.box_series_stats(track) -> {{centers, areas, hit_ratio}}
      ctx.tracking.track_keypoints(stride=2, max_frames=300) -> [{{idx, keypoints}}]
运动: ctx.motion_geometry.optical_flow_lk(frame1, frame2) -> (prev, cur, valid)
      ctx.motion_geometry.compensate_camera_motion(colors, max_frames=160) -> {{colors: {{color: {{resid_center_mag_mean, loom_rate, ...}}}}}}
      ctx.motion_geometry.estimate_camera_yaw(stride=2, max_frames=400) -> {{frame_idx: yaw_deg}}

## 预注入（不要import）
np, cv2, math, re, scipy, EvidenceBundle, Observation, Measurement

## 严格要求
1. 只写 def solve(ctx): ... return EvidenceBundle(...)
2. 不要写 import 语句
3. 不要写 class、helper function、decorator
4. 不要写 try/except
5. 不要用 open()、os、sys
6. 代码不超过 35 行
7. 不返回答案，只返回观测证据

{recipe_section}

```python
def solve(ctx):
"""

RECIPE_TEMPLATE = """## 参考模板（同类任务高准确率）
```python
{recipe_code}
```
基于此模板修改，保留核心 SDK 调用。不要从零重写。"""
