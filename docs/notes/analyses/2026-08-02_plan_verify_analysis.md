---
status: active
date: 2026-08-02
scope: analysis
owner: gaozhe（agent 起草）
related: outputs/plan_verify/（v1_partial 172 题 + v2 全量 670 题）
---

# Plan+Verify 探究全量分析（qwen3-vl-plus，670 题）

> 前置：设计经用户修正（v2）——planner 出「分步计划+每步 evidence 规格」，
> verifier 在隔离上下文中针对各 evidence 出「验收标准+反欺骗检查」，再独立核对帧内容。
> 数据：`outputs/plan_verify/qwen3-vl-plus_plan_verify.jsonl`（v2 全量）、
> `*_v1_partial.jsonl`（v1 盲 checklist，172 题）。
> 前端 Plan+Verify 页可逐样本查看；人工点评存 `human_ratings.json`。

## 1. 总体指标（v2 全量，n=670，0 错误行）

| 指标 | 值 | 备注 |
|------|---|------|
| plan 准确率 | 50.1% | ≈ 随机（public Chance-Freq 52.7%） |
| verify 准确率 | 50.3% | 同上 |
| plan↔verify 一致率 | 78.2% | 两个独立上下文经常错得一样 |
| 双对率 | 39.7% | |
| oracle（任一答对） | 60.7% | 双通道信息上界 |
| verify 救回 / 带偏 | 71 / 70 | 不一致 case 上 verify 无净收益 |

**核心发现 1：双盲一致 ≠ 正确。** 一致 case 的准确率（50.3%）与全局无差——
planner 和 verifier 共享同样的感知错误（与论文结论一致：瓶颈在感知，不在推理）。
**纯文本级的 plan+verify 自洽不能替代真实工具证据。**

## 2. 分任务（v2 首轮 567 题）

| 任务 | n | plan | verify | 亮点 |
|------|---|-----|-------|------|
| Interaction Direction | 28 | **75.0** | 60.7 | plan 强但 verify 反而拖低 |
| Ego Motion | 48 | 64.6 | 58.3 | |
| Relative Velocity | 42 | 61.9 | 61.9 | |
| Swimming Race | 30 | 50.0 | **73.3** | verify 显著提升（唯一正收益大类） |
| Basketball Shot | 48 | 50.0 | 56.2 | verify 小升 |
| Fall Direction | 23 | 30.4 | 34.8 | 重灾区 |
| Jenga Stability | 35 | 31.4 | 28.6 | 重灾区（一致率 97% 却双错） |
| Passage Feasibility | 20 | 35.0 | 40.0 | |

## 3. 置信度完全失校（重要）

| conf 桶 | plan n | plan acc | verify n | verify acc |
|---------|-------:|---------:|---------:|-----------:|
| <60 | 10 | 60.0 | 18 | 55.6 |
| 60–80 | 80 | 50.0 | 44 | 52.3 |
| 80–90 | 278 | 47.5 | 65 | 41.5 |
| 90+ | 196 | 54.6 | 439 | 50.6 |

**自报置信度与准确率零相关**（90+ 自信也只有 50.6%）→ 置信度不可作为路由依据；
必须用 verifier 的**结构化验收结果**（成立/不成立计数）替代。

## 4. 模型自主提出的工具空间（v2 plans，n=567）

| 工具族 | 提及率 | 对应人工设计 |
|--------|-------:|------------|
| 目标检测/跟踪 | **99%** | T1/T3 |
| 局部放大 | **96%** | T9 |
| 轨迹/抛物线拟合 | **90%** | T4 |
| 深度/3D 重建 | 82% | T6 |
| 光流 | 80% | T2 族 |
| 人体姿态估计 | 66% | T5 |
| 时序/帧差分析 | 36% | — |

**核心发现 2：模型自主工具空间与人工设计（tool_design_v1.md 的 T1–T9）高度吻合**——
人工 hack 的工具覆盖面被独立验证；同时说明"让 VLM 自己 plan"得到的解法空间
收敛于同一套感知原语，**差异化竞争力在工具执行质量与证据验收的严格性**。

## 5. 反欺骗机制在真实工作

- 81% 的 self_check 至少抓到一条 evidence「不成立」（458/567）——verifier 确实在审计而非盖章
- 冒烟期即有翻案案例（id=1：planner Yes@95 → verifier No@95，GT=No）
- 但全量看翻案无净收益（60 救回 vs 63 带偏）：**verifier 也只能用同样的 16 帧做判断**，
  感知天花板相同 → 下一步必须给 verifier 真实工具输出（跟踪轨迹、光流量、3D 几何），
  验收才有增量信息

## 6. 对 agent 架构的推论（更新 ADR 依据）

1. plan→execute→verify 链条方向正确，但 **verify 环节必须接工具证据**而非二次裸看帧
2. 验收标准要绑定**可测的量**（像素位移、轨迹残差、净空像素数），v2 的 criteria 文本已展示模型有能力把标准写得可执行（阈值/区域/时刻俱备）
3. 置信度自报无效；用「证据成立率」作为答案可信度的代理信号
4. 任务优先级修正：Jenga/Fall/Passage 是模型裸跑重灾区（30-35%），工具增益空间最大；
   Interaction Direction 裸 plan 已达 75%，verify 要谨慎接入防拖低

## 7. 遗留

- ~~103 题 ConnectionReset~~ 已全部补跑恢复（放宽重试捕获 + 低并发收尾），最终 670/670
- 人工点评（human_ratings.json）与 verifier 判词的对照分析待用户积累点评后做
