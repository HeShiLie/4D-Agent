---
status: completed
date: 2026-08-02
scope: evaluation
plan: docs/working_logs/plans/active/2026-08-01-baseline-and-toolchain-v1.md
---

# Run: Plan+Verify 全量探究（qwen3-vl-plus × 670 题，v2 设计）

## Configuration

| Parameter | Value |
|-----------|-------|
| Runner | `agent/run_plan_verify.py`（双 key 轮换、断点续跑） |
| Model | qwen3-vl-plus @ AMAP 网关（16 帧 640×360 base64） |
| Prompt | v2：planner 出分步计划+evidence 规格；verifier 隔离上下文，对 evidence 出验收标准+反欺骗检查 |
| Output | `outputs/plan_verify/qwen3-vl-plus_plan_verify.jsonl`（670/670） |
| Duration | 首轮 143.7min（ok 567）+ 补跑两轮（103 → 全恢复）≈ 3h 总计 |

## Result（n=670，无错误行）

| 指标 | 值 |
|------|---|
| plan 准确率 | 50.1%（≈ Chance-Freq 52.7% 之下） |
| verify 准确率 | 50.3% |
| plan↔verify 一致率 | 78.2% |
| 双对率 | 39.7% |
| oracle（任一答对） | 60.7% |
| disagree case：verify 救回 / 带偏 | 71 / 70（无净收益） |

## 关键结论（详见 `docs/notes/analyses/2026-08-02_plan_verify_analysis.md`）

1. **双盲一致≠正确**：agree case 准确率与全局无差——两上下文共享感知错误
2. **置信度完全失校**：自报 conf 90+ 也只有 ~51% 准确；须用证据成立率替代
3. **模型自主工具空间 ≈ 人工设计 T1–T9**：检测/跟踪 99%、局部放大 96%、轨迹拟合 90%、深度/3D 82%、光流 80%、姿态 66%
4. **反欺骗机制真实工作**（81% 的 self_check 抓到 evidence 不成立），但 verifier 裸看同样的 16 帧时没有信息增量 → **verify 必须接真实工具输出**
5. 裸跑重灾区：Jenga 31% / Fall 30% / Passage 35%（工具增益空间最大）

## Artifacts

- 全量数据：`outputs/plan_verify/qwen3-vl-plus_plan_verify.jsonl`
- v1 partial（盲 checklist 172 题）：`outputs/plan_verify/qwen3-vl-plus_plan_verify_v1_partial.jsonl`
- 分析报告：`docs/notes/analyses/2026-08-02_plan_verify_analysis.md`
- 前端：Plan+Verify 页（数据源可选 v1/v2、30s 自动刷新、人工点评框）

## Notes

- 网关在高并发下会 Connection reset（103/670 首轮失败）；补跑捕获 OSError 后全恢复；顽固 6 题用 --workers 2 低并发通过
- verify 输入剥离了 planner 答案，仅含 plan 文本（步骤+evidence 规格），隔离成立
