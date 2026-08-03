"""Step 1: Planner — model decides what SDK actions to run.

The model outputs a structured JSON plan (not code).
The pipeline then generates guaranteed-valid Python from this plan.
"""

PLANNER_PROMPT = """你是一个视频分析规划器。看这些视频帧和题目，选择需要执行的分析动作。

【题目】{question}
【选项】{options}

## 可用动作（从中选择 1-3 个最相关的）

1. track_colored_boxes — 跟踪视频中 green/blue 标注框的运动轨迹
   参数: colors (如 ["green","blue"])
   适用: 比较两个标注目标的运动、速度、位置变化

2. compensate_camera_motion — ego 运动补偿，提取目标相对于背景的真实运动
   参数: colors (如 ["green","blue"])
   适用: 驾驶视频中判断哪辆车更快、是否在移动

3. estimate_camera_yaw — 估算相机累计偏航角
   参数: （无）
   适用: 相机运动方向、物体相对于相机的方位

4. track_keypoints — 人体姿态关键点跟踪
   参数: （无）
   适用: 人的动作方向、摔倒方向、身体姿态变化

5. optical_flow — 光流分析（全局运动方向和幅度）
   参数: （无）
   适用: 整体运动趋势、运动区域检测

6. detect_blobs — HSV 颜色区域检测
   参数: hsv_ranges (如 [[[5,180,150],[22,255,255]]]) 和 min_area
   适用: 检测特定颜色物体（锥桶、球等）

7. frame_diff — 帧差分析（运动区域检测）
   参数: （无）
   适用: 检测运动物体、判断是否有运动

8. visual_observation — 不用工具，让 VLM 直接观察帧并描述
   参数: focus (关注什么，如 "物体间的空间关系")
   适用: 空间推理、结构判断、复杂场景理解

输出 JSON（不要写代码）：
```json
{{
  "actions": [
    {{"action": "动作名", "params": {{...}}, "reason": "为什么选这个"}}
  ],
  "judgment_logic": "如何根据结果判断答案"
}}
```"""
