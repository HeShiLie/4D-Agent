---
status: active
scope: benchmark
last_verified: 2026-08-01
owner: gaozhe
source: references/ViSTR-Bench.pdf (arXiv:2607.20868v1, 2026-07-23)
---

# ViSTR-Bench 知识摘要

> 本文档是 `references/ViSTR-Bench.pdf` 的提炼。做 benchmark 相关工作前必读。
> 细节（Appendix 模板全文、逐任务样例）以 PDF 为准。

## 1. Benchmark 概况

- **目标**：评测 MLLM 能否从动态场景的连续视觉线索做**定性**时空推理（temporal emphasis / reasoning orientation / qualitative evaluation 三原则）。
- **规模**：4 维度、15 子任务、**1,340** 个视频 QA 对，全部为**二选一**（选项顺序已随机化以消除位置偏置）。
- **场景**：tabletop / indoor / outdoor；来源 = 公开数据集（584: Waymo, ScanNet/++, ARKitScenes, Ego4D, Motion-X）+ 网络视频（495）+ 自采（261）。
- **划分**：public 670（可下载迭代）/ private held-out 670（官方维护 leaderboard）。**只在 public split 上调参。**
- **指标**：accuracy (%)，总体为全部 QA 对的平均。

## 2. 任务体系（15 子任务）

| 维度 | 子任务 | 样本数 | 问题形式（详见 Appendix B） |
|------|--------|-------:|------|
| Motion Perception (17.9%) | Vehicle Movement | 112 | 绿框车是否有轻微移动？Yes/No |
| | Relative Velocity | 84 | 绿框车 vs 蓝框车谁更快？Green/Blue |
| | Rotation Direction | 145 | 从 {PERSPECTIVE} 看人旋转顺/逆时针？ |
| Spatial Relations (17.0%) | Ego Motion | 131 | 移动相机下目标物最终相对相机方位？{A}/{B} |
| | Passage Feasibility | 55 | 车能否不碰锥桶通过？Yes/No |
| | Interaction Direction | 56 | 人相对 {TARGET} 的运动方向？Upward/Downward 等 |
| Outcome Prediction (44.1%) | Basketball Shot | 124 | 球是否进筐？Yes/No |
| | Soccer Shot | 158 | 任意球是否进（忽略门将）？Yes/No |
| | Golf Shot | 53 | 球是否进洞？Yes/No |
| | Billiards Shot | 75 | 目标球是否进袋？Yes/No |
| | Swimming Race | 72 |  lane {A} vs lane {B} 谁先到？ |
| | Fall Direction | 46 | 人倒向哪个方向？{A}/{B} |
| Physical Dynamics (21.0%) | Jenga Stability | 117 | 抽出该积木后塔是否稳？Yes/No |
| | Mikado Dependency | 83 | 目标签能否不碰其他签拿起？Yes/No |
| | Knot Type | 29 | 活结还是死结？Slip/Fixed |

**数据预处理关键点**（构造防作弊）：事件级裁剪、视觉提示（目标物叠加 bbox，如绿/蓝框）、**结局截断**（在结果显现前手动截断视频）→ 单帧/常识先验答不出来，必须用时序证据。

## 3. 输入协议与评测设置

- 原生视频模型（Gemini, Seed, MiMo, Qwen, GLM）：直接给视频，≤1920×1280，Base64 ≤10MB。
- 纯图像模型（GPT, Claude, InternVL, Intern-S1）：**均匀采样 16 帧**。
- 只评纯视觉+文本模型；不允许额外 GT 3D 信息（深度/位姿真值/点云）作为输入 —— 但**工具估计的**中间证据不在此列（论文 IV-F 自己就这么做的）。

## 4. 榜单（论文 Table II，全集 1,340）

| 模型 | Avg. | 备注 |
|------|-----:|------|
| **Human** | **91.0** | 上界参考 |
| **GPT-5.4-thinking** | **62.0** | 当前榜首 |
| Seed-2.0-Pro-thinking | 60.1 | |
| Seed-2.0-Lite-thinking | 58.8 | |
| Seed-2.0-Pro | 56.8 | |
| GPT-5.4 | 56.1 | |
| Claude-Opus-4.6 | 55.4 | thinking 版反而略降 (54.7) |
| Qwen3.5-27B-thinking | 55.0 | 开源最佳 |
| GeoThinker-Qwen2.5VL-7B | 52.8 | 空间专用模型最佳（≈随机） |
| Chance (Frequency) | 57.9 | 仅 3 个模型超过此线 |
| Chance (Random) | 50.0 | |

**观察**：① 全部模型远低于人类；② 闭源通用 > 开源通用 > 空间专用（静态空间能力不迁移到动态推理）；③ thinking 模式有帮助但不稳定；④ Motion Perception / Spatial Relations 相对好，**Outcome Prediction / Physical Dynamics 接近随机** —— 这是最大的提分空间。

## 5.  prompting / 输入格式实验（Gemini-3.1-Pro 为基座）

- 文本 CoT 收益很小：Direct 53.6 → Zero-shot +0.9 → Self-Consistency +1.0 → Plan-and-Solve +1.3 → **Manual CoT +1.6**（55.2 仍接近随机线）。→ 纯文本推理补不了感知短板。
- 视觉输入：text-only 47.0 → last frame +4.7 → shuffled +4.9 → ordered +5.0 → **original video +6.6**（53.6）。ordered≈shuffled 说明模型几乎不利用连续时序。
- 结局线索诊断（Basketball Shot 20 例）：人类 80→90→100% 随视频比例单调升；Gemini 50→65→60%，**不会利用结局前线索**。

## 6. 错误分析（Gemini-3.1-Pro Manual CoT 的 600 个错误，Table V）

| 错误类型 | 占比 | 含义 | 对策方向 |
|---------|-----:|------|---------|
| Motion State Error | 27.5% | 动没动/谁更快/转向判断错 | 光流、轨迹定量估计 |
| Outcome Reasoning Error | 24.5% | 无法从中间状态外推结局 | 轨迹外推、物理先验 |
| Target Tracking Error | 18.3% | 跨帧跟丢目标（球类高发） | 检测+跟踪器 |
| Physical Interaction Error | 15.8% | 支撑/依赖/稳定性判断错（Jenga/Mikado/Knot） | 接触分析、放大局部 |
| Spatial Relation Error | 12.7% | 自我中心方位/净空判断错 | 3D 重建、新视角 |
| Target Identification Error | 1.2% | 初始定位错（极少） | 基本可忽略 |

## 7. 论文验证过的提分方向（IV-F，打榜核心依据）

1. **Input-centric（输入增强）**：VGGT-Ω 重建场景 + 渲染 10 个辅助新视角 → GPT-5.4 在 **Ego Motion 63.4% → 80.2%（+16.8）**。
2. **Tool-augmented（工具增强）**：WAFT 光流 → Perception Program 式**语言原生紧凑摘要** → **Interaction Direction 78.6% → 83.9%（+5.3）**。
3. 论文明示方向："build agentic systems that decompose complex video reasoning problems into intermediate subproblems and use external tools"（检测/跟踪/光流/3D 重建），把低层感知卸载给工具，MLLM 专注高层推理。

→ **我们的 agent 系统架构决策见 `docs/adr/2026-07-31_tool_augmented_agent_architecture.md`。**

## 8. Public split 实测（2026-08-01 校验，`data/benchmarks/ViSTR-Bench-Public/`）

- 670 样本（id 1–1383 非连续），视频 0 缺失；h264，典型 1920×1080@30fps、数秒片段。
- `data.json` 每题字段：`id / dataset / dimension / task / direct_prompting / manual_cot_prompting / video / answer / options` —— **官方 Manual CoT 模板逐题附带**，无需从 PDF Appendix B 转写。
- 任务/维度名为下划线格式（`Basketball_Shot` / `Outcome_Prediction`），代码里注意与论文空格格式互转。
- 任务分布（public 670）：Soccer 79, Rotation 73, Ego 66, Basketball 62, Jenga 58, Vehicle 56, Mikado 42, Rel.Vel 42, Billiards 38, Swimming 36, Interaction 28, Passage 27, Golf 26, Fall 23, Knot 14。
- 来源含 Bilibili(143)/YouTube(104)/Video(130) 网络视频 + Waymo(98)/Ego4D(76)/MotionX(53)/ScanNet(41)/ARKit(25)。
- 答案取值跨任务多样（Yes/No, Green/Blue, 车道号 2–9, Slip/Fixed, Front-/Back-left/right, Upward/Downward, Left/Right, Clockwise/Counterclockwise…）→ 答案解析必须 per-question 对照 `options` 做。
- **public split Chance(Frequency) = 52.7%**（全集为 57.9%）；迭代时以 public 数字为准。

## 9. 评测注意事项

- 选项顺序已随机化 → 不要假设位置分布；解析答案时做严格匹配 + fallback。
- Chance(Frequency)=57.9%（全集）/ 52.7%（public）是重要参照：任何配置低于此线说明存在系统性失效（如单选项偏置）。
- 空间专用模型有"单选项偏置"前科 → 我们的系统也要监控 per-task 预测分布（前端 Panel C 已覆盖）。
- 视频截断是人工定的"决策点"，时序证据够用但结局不可见 → 不要试图找结局帧。
