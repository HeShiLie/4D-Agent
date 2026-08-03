# ViSTR-Bench Tool-Augmented Agent — 实验报告

## 1. 任务概述

**目标**: 在 ViSTR-Bench 公开集 (670 binary-choice video QA) 上达到 ≥60% 准确率。

**Baseline**: qwen3-vl-plus 直接作答（10帧 + 题目）= **50.1%** (chance-freq = 52.7%)

**当前最优整合结果**: **55.8%** (eval split 57.3%)

**模型**: qwen3-vl-plus (通过 AMAP 网关, OpenAI-compatible API)

**数据划分**: stratified dev/eval = 403/267, seed=20260802, 按 task 分层

---

## 2. 15 个 Subtask 一览

| Task | 维度 | 样本数 | Baseline(eval) | 当前最优(eval) | 提升 | 方法 |
|------|------|--------|---------------|---------------|------|------|
| Relative_Velocity | Motion | 42 | 58.8% | **82.4%** | +23.6 | 纯工具决策 |
| Swimming_Race | Motion | 36 | 57.1% | **78.6%** | +21.5 | verify fallback |
| Interaction_Direction | Spatial | 28 | 72.7% | 72.7% | 0 | plan fallback |
| Basketball_Shot | Outcome | 62 | 68.0% | 68.0% | 0 | verify fallback |
| Fall_Direction | Motion | 23 | 22.2% | **66.7%** | +44.5 | VLM+evidence |
| Knot_Type | Physical | 14 | 66.7% | 66.7% | 0 | plan fallback |
| Rotation_Direction | Motion | 73 | 41.4% | **62.1%** | +20.7 | 工具覆盖门控 |
| Soccer_Shot | Outcome | 79 | 59.4% | 59.4% | 0 | plan fallback |
| Passage_Feasibility | Spatial | 27 | 27.3% | **54.5%** | +27.2 | VLM+evidence |
| Billiards_Shot | Outcome | 38 | 53.3% | 53.3% | 0 | plan fallback |
| Vehicle_Movement | Motion | 56 | 27.3% | **50.0%** | +22.7 | VLM+evidence |
| Golf_Shot | Outcome | 26 | 50.0% | 50.0% | 0 | plan fallback |
| Ego_Motion | Motion | 66 | 53.8% | 50.0% | -3.8 | verify fallback |
| Mikado_Dependency | Physical | 42 | 35.3% | 35.3% | 0 | plan fallback |
| Jenga_Stability | Physical | 58 | 30.4% | 30.4% | 0 | plan fallback |

---

## 3. 工具管线详细设计

### 3.1 Relative_Velocity — 纯工具决策（eval 82.4%）

**问题**: 绿框车和蓝框车谁速度更快？

**管线**:
```
Video → HSV 颜色检测定位绿框/蓝框区域 (ground_track.py)
     → 全帧 LK 稀疏光流跟踪（Shi-Tomasi 角点）
     → 背景点筛选（排除框内点）
     → RANSAC 拟合背景 partial affine（ego-motion 补偿）
     → 对每个框内目标计算补偿后残差:
       - resid_center_mag_mean: 残差位移均值 (px/帧)
     → 决策: green.resid_mag > blue.resid_mag → "Green" else "Blue"
```

**关键代码**: `agent/tools/ground_track.py` + `agent/tools/motion.py`

**特点**: 
- 不调用 VLM，纯 CV 计算
- Ego-motion 补偿是核心（大部分光流来自自车运动）
- 比较两个目标的相对运动量，不需要绝对阈值

---

### 3.2 Rotation_Direction — 工具覆盖门控（eval 62.1%）

**问题**: 人的旋转方向是顺时针还是逆时针？

**管线**:
```
Video → YOLOv8n-pose 逐帧检测人体17关键点 (pose_motion.py)
     → 提取鼻子(nose)和肩中点(mid-shoulder)
     → 计算归一化水平偏移序列: (nose_x - mid_shoulder_x) / shoulder_width
     → 前半段累计速度 vel_sum = sum(diff(序列前50%))
     → 覆盖门控:
       |vel_sum| ≥ 0.8 → 工具直出: vel_sum < 0 → "Clockwise", > 0 → "Counterclockwise"
       |vel_sum| < 0.8 → 信号不足，放弃工具，fallback 到 plan/verify
```

**关键代码**: `agent/tools/pose_motion.py` → `analyze_rotation()`

**特点**:
- 原理: 人转动时鼻子相对肩膀中心的左右摆动方向 = 旋转方向的投影
- vel_sum < 0 表示鼻子向画面左移（面部从正面转向右侧 → 顺时针）
- 覆盖门控避免低信噪比样本（信号弱时工具不可靠）
- 约 55% 样本被工具覆盖（|vel_sum| ≥ 0.8）

---

### 3.3 Fall_Direction — VLM+evidence（eval 66.7%）

**问题**: 人倒向哪边？（Left/Right/Lie down）

**管线**:
```
Video → YOLOv8n-pose 逐帧检测 (pose_motion.py)
     → 计算肩-髋水平错位序列: shoulder_center_x - hip_center_x
     → 线性回归得 lean_trend（倾斜趋势，负=左倾）
     → 首末段均值: lean_start, lean_end
     → 末段躯干倾角 end_abs_angle (arctan of shoulder-hip vector)
     → 构造证据文本:
       "倾倒趋势=-0.023, 起始+0.02→末段-0.15, 末段躯干倾角68°"
     → 喂给 qwen3-vl-plus (10帧 + 证据文本)
     → VLM 综合视觉+数值输出最终答案
```

**关键代码**: `agent/tools/pose_motion.py` → `analyze_fall()`, `agent/eval_vlm_evidence2.py`

**特点**:
- 工具单独决策时 dev 准确率尚可但 eval 不够稳定
- VLM+evidence 模式: 工具提供量化趋势，VLM 做最终判断
- lean_trend 的符号（正/负）是最强信号

---

### 3.4 Vehicle_Movement — VLM+evidence（eval 50.0%, baseline 27.3%）

**问题**: 绿框标注的车有没有在动？(Yes/No)

**管线**:
```
Video → HSV 绿框检测定位目标车区域 (ground_track.py)
     → 背景 LK 光流 + RANSAC partial affine 补偿 ego-motion (motion.py)
     → 目标区域补偿后运动特征:
       - resid_center_mag_mean: 质心残差活动量 (px/帧)
       - resid_center_net: 质心净漂移
       - epi_net_signed: 基础矩阵对极几何带符号净偏差
       - loom_rate: 目标面积变化率（逼近/远离）
     → 构造证据文本 + 参考阈值说明:
       "静车这些量接近0; 移动车通常残差/净偏差明显非零"
     → 喂给 qwen3-vl-plus (10帧 + 证据)
     → VLM 输出 Yes/No
```

**关键代码**: `agent/tools/motion.py`, `agent/eval_vlm_evidence.py`

**特点**:
- 纯工具决策不可行: Yes/No 的 resid_mag 分布严重重叠（中位数差距小）
- ego-motion 补偿后残差仍有大量 parallax 噪声（近处静止物体因深度差产生大残差）
- VLM+evidence 翻倍了准确率（27.3% → 50.0%），但仍未超过 60%
- 对极几何(fundamental matrix)尝试独立检测运动，但精度有限

---

### 3.5 Passage_Feasibility — VLM+evidence（eval 54.5%, baseline 27.3%）

**问题**: 车能不能穿过锥桶门？(Yes/No)

**管线**:
```
Video → HSV 橙色检测锥桶 (passage.py)
     → 最后一帧最近锥桶对 → 门宽 gate_gap_px
     → 帧差法检测运动车辆 blob → 最大宽度 vehicle_max_width_px
     → margin_ratio = gate_gap / vehicle_width
     → 构造证据文本 + 参考判据:
       "比值<1 必然碰撞; 1~1.3 临界; >1.3 较安全"
     → 喂给 qwen3-vl-plus (10帧 + 证据)
     → VLM 输出 Yes/No
```

**关键代码**: `agent/tools/passage.py`, `agent/eval_vlm_evidence.py`

**特点**:
- 几何测量直觉正确: 门宽/车宽比 < 1 → 必撞
- 但 scale=0.5 下分辨率有限，锥桶/车辆宽度测量有噪声
- margin_ratio 单独做二值分类不够，VLM 辅助判断提升明显

---

### 3.6 Swimming_Race — verify fallback（eval 78.6%）

**问题**: Lane X 和 Lane Y 谁先到终点？

**管线**:
```
Question → plan+verify 流程中的 verify 答案直接作为最终答案
（工具 swim.py 计算了泳道运动团块跟踪，但 VLM+evidence 反而降低准确率）
```

**已实现但未使用的工具** (`agent/tools/swim.py`):
```
Video → resize 0.5x → 灰度帧差 → 二值化+膨胀
     → 按泳道带(8等分 pool 区域)切片
     → 每泳道运动像素的 mean_x / percentile_90 时间序列
     → 线性回归得 vel (平均速度) 和 vel90 (前缘速度)
     → 证据: "lane3 vel=+1.39px/f, lane7 vel=+0.44px/f"
```

**为什么工具没用**: 
- 泳道识别不精确（假设8等分，实际视角/泳池不一定符合）
- 速度方向对终点位置的映射不确定（有的视频泳向左，有的向右）
- verify 本身在该 task 上意外表现极好（78.6%），可能是 qwen 对泳道竞赛视频有较好的 pre-training 覆盖

---

## 4. 尝试过但失败的工具

### 4.1 Jenga_Stability（eval 30.4% = baseline）
**思路**: 检测塔轮廓 → 塔顶位移/晃动量
**失败原因**: 塔身轮廓在抽块前后变化微小，wobble_ratio 信噪比不够区分"稳定"和"倒塌前兆"。VLM+evidence 反而降到 27.3%。

### 4.2 Soccer_Shot（eval 59.4% = baseline）
**思路**: VLM grounding 球+门柱坐标 → 抛物线拟合 → 判断是否穿过球门线
**失败原因**: qwen grounding 精度不够（球小且快速运动），轨迹拟合噪声大，min_dist 判据不可靠。VLM+evidence 降到 50.0%。

### 4.3 Ego_Motion（eval 50.0%, baseline 53.8%）
**思路**: VLM grounding 目标物方位 + 视觉里程计(essential matrix → cumulative yaw)
**失败原因**: 室内长视频 yaw 估计漂移严重；前/后方向混淆（180°歧义）；VLM grounding "在你前方/后方"不够精确。

---

## 5. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Per-sample Router                      │
│  (根据 task 类型选择策略)                                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 纯工具决策    │  │ VLM+evidence │  │  VLM fallback │  │
│  │              │  │              │  │              │  │
│  │ RelVel:      │  │ VM: motion   │  │ Swimming:    │  │
│  │  resid比较   │  │  features →  │  │  verify ans  │  │
│  │              │  │  qwen+10帧   │  │              │  │
│  │ Rotation:    │  │              │  │ Basketball:  │  │
│  │  vel_sum门控 │  │ Fall: pose   │  │  verify ans  │  │
│  │  (>0.8才出)  │  │  lean →      │  │              │  │
│  │              │  │  qwen+10帧   │  │ Others:      │  │
│  │              │  │              │  │  plan/verify  │  │
│  │              │  │ Passage:     │  │  (dev-chosen) │  │
│  │              │  │  geometry →  │  │              │  │
│  │              │  │  qwen+10帧   │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 6. 核心 CV 技术栈

| 技术 | 用途 | 文件 |
|------|------|------|
| LK 稀疏光流 | 背景运动估计 | motion.py |
| RANSAC partial affine | ego-motion 补偿 | motion.py |
| Fundamental matrix (8-point) | 独立运动对极检测 | motion.py |
| HSV 颜色分割 | 绿/蓝框、橙色锥桶检测 | ground_track.py, passage.py |
| YOLOv8n-pose | 人体关键点 | pose_motion.py |
| Template matching (NCC) | 目标存在性验证 | presence.py |
| 帧差法 + 形态学 | 运动物体检测 | passage.py, swim.py |

---

## 7. 瓶颈分析

### 能打的任务（+20pp 以上）都有什么共性？
1. **明确的视觉信号**: 颜色框(RelVel/VM)、人体骨架(Rotation/Fall)、锥桶颜色(Passage)
2. **可量化的比较**: 两个目标比大小(RelVel)、方向正负(Rotation/Fall)、比值阈值(Passage)
3. **短时间内信号明显**: 不需要长程推理

### 打不动的任务缺什么？
1. **Jenga/Mikado**: 需要细粒度物理接触关系理解（哪块积木/木棒支撑着哪个），需要实例分割+接触图
2. **Soccer/Golf/Basketball**: 需要精准小球检测+跟踪（像素级别），当前 VLM grounding 精度不够
3. **Ego_Motion**: 需要鲁棒的视觉定位（SLAM级别），当前简单 essential matrix 不够
4. **Billiards**: 需要物理仿真（碰撞后多球轨迹预测）

---

## 8. 数值汇总

**当前整合 (全670样本)**: 55.8%  
**Eval split (267样本)**: 57.3%  
**Baseline**: 50.1% (全) / 48.3% (eval)  
**距离目标 60% 还差**: ~29 个正确答案  

**工具有效覆盖的样本数**: ~220/670 (RelVel 42 + Rotation 73 + Fall 23 + VM 56 + Passage 27)  
**其余 ~450 样本**: 依赖 VLM 自身能力（plan/verify fallback），基本等于 baseline

---

## 9. 文件索引

```
agent/
├── llm.py                  # API client (key rotation, retry)
├── prompts.py              # plan+verify prompt templates (v2)
├── run_plan_verify.py      # 670-sample batch runner
├── eval_integrated.py      # 整合评测 (per-task routing)
├── eval_vlm_evidence.py    # VLM+evidence: VM/Passage/Jenga/Soccer
├── eval_vlm_evidence2.py   # VLM+evidence: Rotation/Fall/Swimming
├── eval_motion.py          # driving tasks threshold sweep
├── eval_pose.py            # rotation+fall tool evaluation
├── eval_jenga.py           # jenga evidence evaluation
├── eval_ego.py             # ego motion evaluation
├── eval_soccer.py          # soccer trajectory evaluation
└── tools/
    ├── __init__.py         # evidence schema + BENCH_DIR/PROJ_DIR
    ├── frames.py           # video_info + iter_frames utilities
    ├── ground_track.py     # HSV box detection + tracking
    ├── motion.py           # ego-compensated motion analysis
    ├── presence.py         # template-match presence check
    ├── pose_motion.py      # YOLOv8n-pose rotation/fall
    ├── jenga.py            # tower silhouette dynamics
    ├── passage.py          # cone gate geometry
    ├── swim.py             # lane progress tracking
    ├── ego_odom.py         # visual odometry (essential matrix yaw)
    └── qwen_ground.py      # VLM target grounding

configs/
├── split.json              # dev/eval stratified split
└── baseline_direct.json    # per-sample baseline answers

outputs/
├── plan_verify/            # 670 plan+verify results
├── tool_runs/              # per-tool evidence caches (jsonl)
└── predictions/            # final integrated predictions
```
