---
status: active
scope: general
last_verified: 2026-07-31
owner: gaozhe
---

# Output Registry

Index of all output directories and artifacts produced by this project.

## Format

```markdown
### Output Name
**Path**: `path/to/outputs/`
**Produced by**: Which script generates this
**Format**: File types and structure
**Notes**: Retention policy, dependencies, etc.
```

---

### Prediction results
**Path**: `outputs/predictions/`
**Produced by**: agent 评测管线（规划中）；mock 数据由 `visualize_results.py --demo` 生成
**Format**: JSONL，每行一个样本：
  `{id, task, dimension, question, options, gt, pred, correct, reasoning, evidence, video, video_relpath}`
**Notes**: 命名约定 `<model>_<config>_<date>.jsonl`（如 `gpt54_direct_0731.jsonl`）；每次实验必须在 `docs/working_logs/runs/` 有对应 run log

### Plan+Verify results（二阶段探究）
**Path**: `outputs/plan_verify/`
**Produced by**: `agent/run_plan_verify.py`
**Format**: JSONL，每行 `{id, task, gt, options, video, plan:{plan_text,answer,confidence,correct,raw}, verify:{checklist,self_check,answer,confidence,correct,raw}, agree, elapsed_s}`
**Notes**: 前端 Plan+Verify 页直接读取；断点续跑按 id 去重

### Visualization outputs
**Path**: `data/visualizations/`
**Produced by**: `visualize_results.py`（经 `scripts/visualize.sh`）
**Format**: `overview_dashboard.png`（leaderboard/任务热力图/错误分布）+ `samples/<id>_replay.mp4`（样本回放）
**Notes**: mp4 为 ffmpeg libx264 编码；样本回放用于 case 分析，可定期清理

### Task posters
**Path**: `web/posters/`
**Produced by**: `scripts/gen_task_posters.py`
**Format**: 15 张 480×270 JPG（每任务一帧代表帧）
**Notes**: taxonomy 页用；benchmark 数据更新后需重新生成
