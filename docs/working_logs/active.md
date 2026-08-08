---
status: active
last_updated: 2026-08-08
---

# ViSTR-Agent — Active Work State

## Current Focus: S2.6 Evidence Closure — answer-time visual verification

pi (v0.84.0) harness + extension 路线持续推进。S2.6 在 S2.4b 观察原语基础上增加
**evidence closure gate**: silent ledger 后台记录观察来源,agent 提交答案时检查关键事实
是否有直接视觉证据闭合,如有缺口允许一次 re-observation。

**S2.6 结果**: 90 题均匀子集 **62.2%** (S2.4b: 56.7%, +5.5pp; SpatialClaw: 56.6%)

**Stage progression**:
- S2.1–S2.4b: 观察原语(how to observe) → 56.7%
- S2.5: evidence board 注入(改变模型推理心态,中性结果) → 54.4~56.7%
- **S2.6: evidence closure gate(when to stop reasoning and re-observe) → 62.2%**

**Pi extensions**(`agent/pi_ext/`):
- `vistr_video_tools.ts` — 5 观察工具(index/sequence/multiframe/crop/semantic_crop)
- `evidence_closure.ts` — S2.6: silent ledger + `submit_answer` 工具 + VLM closure checker
- `evidence_ledger.ts` — S2.5: context 注入 evidence board(当前不加载)

**基础设施**: `scripts/perception_service.py` — 常驻 perception model-pool(:7876,
GroundingDINO GPU 常驻 MI308X);启动:
`nohup .../star/bin/python -u scripts/perception_service.py --port 7876 --eager &`

**评测约定**: 默认 `--per-task 6`(90 题);全量仅用户明确要求。

**Next 候选**:
1. S2.6 full-split eval (403 samples) 确认总体提升
2. 改进 re-observation guidance (告诉 agent 具体看哪个时间段)
3. 运动感知弱项(Fall/RelVel):光流/跟踪后端进 model pool
4. opus + 全套原语 + closure

## Key Results Summary

| Configuration | Accuracy | Samples |
|---------------|----------|---------|
| qwen3-vl-plus baseline | 50.6% | 403 |
| qwen3-vl-plus via pi S1(纯问答) | 54.6% | 403 |
| qwen3-vl-plus + V4 tools | 55.6% | 403 |
| SpatialClaw | 56.6% | 403 |
| claude-opus-4-6 via pi S1 | 57.1% | 403 |
| pi S2.4b(全套观察原语) | 56.7% | 90(均匀) |
| pi S2.5 evidence board(tail/anchor) | 54.4~56.7% | 90(均匀) |
| **pi S2.6 evidence closure** | **62.2%** | 90(均匀) |
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
