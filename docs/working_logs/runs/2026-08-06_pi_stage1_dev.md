---
status: active
scope: evaluation
last_verified: 2026-08-06
owner: gaozhe
---

# Run Log — pi harness Stage 1 全量 dev 评测

- **Date**: 2026-08-06
- **Script**: `agent/eval_pi.py --split dev --workers 4 --resume`
- **Harness**: pi v0.84.0 (`third_party/pi-runtime/`), print 模式,无工具
- **Model**: qwen3-vl-plus via AMAP gateway (`~/.pi/agent/models.json`)
- **Output**: `outputs/predictions/pi_qwen3-vl-plus_dev_20260806.jsonl`
- **Log**: `outputs/predictions/pi_dev_20260806.log`

## Result

**220/403 = 54.6%**,0 errors,21.4s/样本(4 并发实际 5.4s/样本,总耗时 36 min)

| Task | Acc | vs V4 (55.6% run) |
|------|-----|------|
| Interaction_Direction | 76% | 82% |
| Vehicle_Movement | 71% | 71% |
| Relative_Velocity | 68% | 64% |
| Ego_Motion | 62% | 60% |
| Golf_Shot | 62% | 44% |
| Knot_Type | 62% | 75% |
| Passage_Feasibility | 62% | 69% |
| Soccer_Shot | 55% | 49% |
| Mikado_Dependency | 52% | 48% |
| Fall_Direction | 50% | 43% |
| Rotation_Direction | 50% | 50% |
| Basketball_Shot | 43% | 65% |
| Billiards_Shot | 43% | 48% |
| Swimming_Race | 41% | 45% |
| Jenga_Stability | 37% | 40% |

## Baseline 对比

| Configuration | Accuracy |
|---------------|----------|
| qwen3-vl-plus 裸 API baseline | 50.6% |
| **qwen3-vl-plus via pi (Stage 1, 无工具)** | **54.6%** |
| qwen3-vl-plus + V4 tools | 55.6% |

## Observations

1. **pi 无工具已超裸 API baseline +4pp**(54.6% vs 50.6%),仅差 V4 全工具版 1pp——pi 的 system prompt/对话框架本身提升了模型表现
2. **"No" bias 明显缓解**:Yes/No 题 pred Yes 46%(gt 56%);此前裸 API 强烈偏 No
3. 预测类任务提升显著:Golf_Shot 44%→62%, Soccer_Shot 49%→55%;但 Basketball_Shot 65%→43% 回退
4. 0 网关错误,4 并发稳定

## Next

- Stage 2:启用 pi 工具能力(bash/read + 帧目录工作区),对齐 V4 工具证据路径
