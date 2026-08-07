---
status: active
last_updated: 2026-08-07
---

# ViSTR-Agent — Active Work State

## Current Focus: pi harness 观察原语体系(已完成四阶段)

pi (v0.84.0) 为 harness;通过 extension 逐步构建 task-agnostic 观察原语,
**只改观察接口不教任务解法**,qwen3-vl-plus 在 90 题均匀子集上 50.0% → **56.7%**,
首超 SpatialClaw(53.3%)。计划书: `plans/completed/0807-[pi作为harness]stage2.1-pi+多图阅读工具.md`,
run log: `runs/2026-08-07_pi_observation_primitives.md`。

**观察原语四件套**(`agent/pi_ext/vistr_video_tools.ts`):
- `read`(pi 原生)单帧 | `read_crop` normalized bbox 空间放大
- `read_video_sequence` 连续时间片段 | `read_multiframe` 离散证据帧联查
- `index_video` batch VLM caption 时间线(无题目上下文)
- `semantic_crop` 文字描述 → GroundingDINO 定位 → 隔离 VLM 选候选 → 高清裁剪+回执

**基础设施**: `scripts/perception_service.py` — 常驻 perception model-pool(:7876,
GroundingDINO GPU 常驻 MI308X;可扩 SAM2/DA3/VGGT);启动:
`nohup .../star/bin/python -u scripts/perception_service.py --port 7876 --eager &`

**评测约定**: 默认 `--per-task 6`(90 题);全量仅用户明确要求。

**其他资产**: Case viewer(Flask :7875,S1/S2/S2.1/S2.2 轨迹 tab 切换);
opus S1 全量 57.1%;HF 轨迹数据集 MihailSlutsky/vistr-pi-trajectories。

**Next 候选**:
1. 运动感知三弱项(Fall/RelVel/Vehicle 各 1/6):光流/跟踪后端进 model pool
2. 观察策略融合(S2.x oracle 76.7%)
3. opus + 全套原语

## Key Results Summary

| Configuration | Accuracy | Samples |
|---------------|----------|---------|
| qwen3-vl-plus baseline | 50.6% | 403 |
| qwen3-vl-plus via pi S1(纯问答) | 54.6% | 403 |
| qwen3-vl-plus + V4 tools | 55.6% | 403 |
| SpatialClaw | 56.6% | 403 |
| claude-opus-4-6 via pi S1 | 57.1% | 403 |
| **pi S2.4b(全套观察原语)** | **56.7%** | 90(均匀) |
| qwen3-vl-8b-thinking baseline | 50.6% | 403 |

两模型互补：8b-thinking 擅长预测类 (Soccer +23pp, Golf +12pp)，plus 擅长空间感知 (Passage +19pp, Ego +18pp)。

## History

### V4 Action Plan Pipeline (2026-08-02 ~ 08-03)

**架构**: Planner(JSON actions) → Action Executor(预建代码) → Hybrid Verify(VLM observe + tool evidence)

**核心组件**:
- `agent/coding_agent/action_executor.py` — 8 种动作映射到确定性 SDK 调用
- `agent/coding_agent/prompts/planner.py` — 模型选择 1-3 个动作的 JSON 计划
- `agent/coding_agent/pipeline.py` — 三路径: hybrid(VLM+tool) / vlm_observe_judge / vlm_fallback

**Pipeline 流程**:
1. Planner → 模型看帧+题目，输出 JSON 动作列表
2. Recipe 检查 → 内容匹配 recipe 则用 sandbox 执行
3. Action executor → 预建代码执行动作，无需 sandbox
4. Hybrid verify → VLM 先观察帧，再结合 tool 证据判断
5. Fallback → 工具全部失败时 VLM observe+judge

**全量 dev 结果 (403 samples): 55.6%**

| Source | Accuracy | Count | 说明 |
|--------|----------|-------|------|
| action_plan | 66% | 61 | 仅工具证据 (Vehicle_Movement, Relative_Velocity) |
| hybrid | 55% | 176 | VLM observe + tool 证据 |
| vlm_fallback | 57% | 80 | 工具失败 → VLM |
| vlm_observe_judge | 48% | 86 | 纯 VLM |

Per-task breakdown:
| Task | Accuracy | 主要路径 |
|------|----------|---------|
| Interaction_Direction | **82%** | vlm_fallback |
| Knot_Type | **75%** | vlm_observe_judge |
| Vehicle_Movement | **71%** | action_plan |
| Passage_Feasibility | **69%** | hybrid |
| Basketball_Shot | 65% | hybrid |
| Relative_Velocity | 64% | action_plan |
| Ego_Motion | 60% | hybrid |
| Rotation_Direction | 50% | vlm_fallback |
| Soccer_Shot | 49% | hybrid |
| Billiards_Shot | 48% | hybrid |
| Mikado_Dependency | 48% | vlm_observe_judge |
| Swimming_Race | 45% | hybrid/VLM |
| Golf_Shot | 44% | hybrid |
| Fall_Direction | 43% | vlm_fallback |
| Jenga_Stability | 40% | vlm_observe_judge |

### 关键发现

1. **模型能正确选择工具**: compensate_camera_motion → 速度类, estimate_camera_yaw → ego 运动, track_keypoints → 人体动作
2. **torch 不可用** → track_keypoints 总失败 → Fall_Direction/Rotation_Direction/Interaction_Direction 走 VLM fallback
3. **工具证据双刃剑**: 对 Vehicle_Movement (+21pp vs random) 帮助巨大, 对 Soccer_Shot/Golf_Shot 基本无用
4. **VLM "No" bias**: qwen3-vl-plus 对预测类问题（"是否进球"）强烈偏向"No"
5. **Hybrid > Tool-only > VLM-only**: 对大多数有工具证据的任务，hybrid verify (VLM+tool) 效果最好

### 版本对比
| Version | Accuracy | Architecture |
|---------|----------|-------------|
| V1 generic+recipe (task routing) | 51.4% | 硬编码 task 路由 |
| V2 observe+judge+recipe | **57.8%** | recipe + VLM fallback |
| V3 free-form codegen | ~25% code success | 模型写 Python |
| **V4 action plan (hybrid)** | **55.6%** | 模型选动作 → 预建代码 → VLM+tool verify |

### 瓶颈分析
- **模型能力上限**: qwen3-vl-plus 在纯视觉预测任务（shot prediction, stability）上约 50%
- **torch 不可用**: 人体姿态/关键点工具无法运行
- **VLM bias**: 预测类问题强烈偏向否定答案

## Active plans

- Phase 4 plan: 已完成核心实现

## Next recommended action

1. **安装 torch** 启用关键点跟踪 → Fall_Direction (+), Rotation_Direction (+)
2. **改进 VLM prompts** → 减少 "No" bias (但 CoT 测试显示效果不大)
3. **增加 recipe 覆盖** → 为 Ego_Motion, Basketball_Shot 写专用 recipe
4. **混合策略**: 用 V2 的 recipe 结果合并 V4 的 VLM 结果, 取每个 task 的最优
5. **换模型**: 测试 qwen3-vl-max 或其他更强 VLM

## Do not do

- 不在 private held-out set 上调参
- 未经确认不跑大规模 GPU 批量评测
- API keys 只存 `agent/llm_keys.local.json`（chmod 600）
