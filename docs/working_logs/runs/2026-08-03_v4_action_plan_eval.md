---
date: 2026-08-03
experiment: V4 Action Plan Pipeline
result: 55.6%
samples: 403 (dev split)
output: outputs/predictions/coding_agent_v4_hybrid.jsonl
---

# V4 Action Plan Pipeline — Full Dev Eval

## Architecture

Model-driven pipeline replacing free-form codegen:
1. **Planner**: qwen3-vl-plus sees 8 frames + question → selects 1-3 actions from 8 predefined types
2. **Action Executor**: deterministic SDK code for each action (no sandbox needed)
3. **Hybrid Verify**: VLM observe frames → judge with both visual observations + tool evidence

Key change from V3: no model-generated Python code. Actions are pre-built, guaranteed to execute.

## New files
- `agent/coding_agent/action_executor.py` — 8 action handlers
- `agent/coding_agent/prompts/planner.py` — JSON action plan prompt
- Updated `pipeline.py` — three-path routing

## Results

**Overall: 224/403 = 55.6%** (19.0s/sample avg, ~2.1 hr total)

### Per-source
| Source | Correct/Total | Accuracy |
|--------|---------------|----------|
| action_plan (tool-only verify) | 40/61 | 66% |
| hybrid (VLM observe + tool) | 97/176 | 55% |
| vlm_fallback (tools fail → VLM) | 46/80 | 57% |
| vlm_observe_judge (VLM-only) | 41/86 | 48% |

### Per-task
| Task | Acc | n | Notes |
|------|-----|---|-------|
| Interaction_Direction | 82% | 17 | VLM fallback works great |
| Knot_Type | 75% | 8 | VLM observe+judge |
| Vehicle_Movement | 71% | 34 | Tool: compensate_camera_motion |
| Passage_Feasibility | 69% | 16 | Tool: track_colored_boxes |
| Basketball_Shot | 65% | 37 | Hybrid: detect_blobs + VLM |
| Relative_Velocity | 64% | 25 | Tool: compensate_camera_motion |
| Ego_Motion | 60% | 40 | Hybrid: estimate_camera_yaw + VLM |
| Rotation_Direction | 50% | 44 | VLM fallback (keypoints fail) |
| Soccer_Shot | 49% | 47 | "No" bias dominates |
| Billiards_Shot | 48% | 23 | "No" bias |
| Mikado_Dependency | 48% | 25 | VLM observe+judge |
| Swimming_Race | 45% | 22 | VLM, hard counting task |
| Golf_Shot | 44% | 16 | "No" bias |
| Fall_Direction | 43% | 14 | VLM fallback (keypoints fail) |
| Jenga_Stability | 40% | 35 | VLM "No" bias |

## Experiments tried during iteration

1. **V4 hybrid** (this run): 55.6% — VLM observe + tool evidence for all
2. **V4c quality gate**: ~54% (stopped early) — skip tools for weak actions → Basketball dropped
3. **V4d refined routing**: ~55% (stopped early) — direct/supplement/VLM categories
4. **CoT vs observe+judge**: CoT was worse (33% vs 61% on VLM-heavy tasks)

## Key findings

1. **Model correctly selects actions**: compensate_camera_motion for velocity, yaw for ego motion
2. **torch unavailable** → keypoint tracking fails → Fall_Direction, Rotation_Direction walk VLM fallback
3. **Tool evidence is a double-edged sword**: helps Vehicle_Movement (+21pp), hurts via VLM bias for shots
4. **VLM "No" bias**: qwen3-vl-plus defaults to "No" for prediction questions (93% of Soccer_Shot predictions are "No")
5. **Hybrid verify > tool-only verify**: VLM observation prevents tool evidence from completely misleading the verifier

## Comparison with prior versions
| Version | Accuracy | Notes |
|---------|----------|-------|
| V2 (best prior) | 57.8% | Recipe + VLM observe+judge |
| V4 (this) | 55.6% | Model-driven action plan |
| V1 (task routing) | 51.4% | Hardcoded task router |

## Bottleneck analysis

The 55.6% ceiling is primarily limited by:
1. **VLM model capability** (~50% on pure visual prediction tasks)
2. **No GPU/torch** (keypoint tools disabled)
3. **"No" prediction bias** (affects 5 tasks: Soccer, Golf, Basketball, Billiards, Jenga)
