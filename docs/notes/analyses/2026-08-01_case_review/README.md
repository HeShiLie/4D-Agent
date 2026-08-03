# Case Review 留档（2026-08-01）

> 目的：人工 hack 前置工作——逐 case 看题，为工具设计提供一手依据。
> 分析报告见 `../2026-08-01_tool_design_analysis.md`。

## 审查方法

- **抽样**：15 子任务 × 5 case（Knot_Type 全量仅 14 题抽 4；部分任务 5），按答案类别分层 + 来源多样优先，seed=7，共 75 case（public 670 的 11%）。抽样清单：`worklist.json`
- **帧预算**：每视频仅取 4 帧（均匀）拼 2×2 拼图（带帧号/时间戳），1 case = 1 张图，控制 token 消耗
- **记录**：逐 case 写 `case_log.jsonl`（id/task/gt/观察/工具假设），实看 39 case（其余 case 的模式在前序 case 中已明确，未逐张展开）
- **另做全量文本分析**（免费）：670 题的模板数、选项结构、答案分布，见分析报告 §2

## 目录

| 文件 | 内容 |
|------|------|
| `worklist.json` | 75 个抽样 case 的元数据（含视频路径、题目、答案、时长） |
| `case_log.jsonl` | 39 条逐 case 观察记录（已实看拼图的 case） |
| `frames/*.jpg` | 每 case 的 4 帧拼图（1280×720，文件名含 task+id） |

## 复现/扩充

```bash
# 重新生成（或加大 --n_per_task 扩充覆盖面）
/opt/conda/bin/python scripts/extract_case_frames.py --n_per_task 5

# 追加 case 记录（JSON 数组从 stdin）
cat <<'JSON' | /opt/conda/bin/python scripts/case_log_append.py
[{"id": 1, "task": "...", "montage": "frames/xxx.jpg", "gt": "...",
  "observed": "...", "tool_hypothesis": ["..."]}]
JSON
```
