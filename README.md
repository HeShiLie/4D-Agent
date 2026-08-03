# ViSTR-Agent

Tool-augmented VLM agent for the [ViSTR-Bench](https://arxiv.org/abs/2501.13253) leaderboard — visual spatial-temporal reasoning from continuous video cues.

## Architecture

**Model-driven action plan pipeline** (V4):

```
Video + Question
       │
       ▼
┌─────────────┐     8 predefined tool actions
│   Planner   │────▶ (track, flow, yaw, blobs, ...)
│ (qwen3-vl)  │     Model selects 1-3 actions
└─────────────┘
       │
       ▼
┌─────────────┐     Deterministic SDK code
│  Executor   │────▶ No sandbox failures
│ (pre-built) │     Guaranteed execution
└─────────────┘
       │
       ▼
┌─────────────┐     VLM observe frames first
│  Verifier   │────▶ Then judge with tool evidence
│ (hybrid)    │     as supplementary reference
└─────────────┘
       │
       ▼
   Final Answer
```

Key design: **no hardcoded task routing**. The VLM autonomously decides which tools to use based on the question content.

## Results

**55.6%** overall accuracy on the public dev set (403 samples, 15 subtasks).

| Category | Best Tasks | Accuracy |
|----------|-----------|----------|
| Strong tool evidence | Vehicle_Movement, Relative_Velocity | 64-71% |
| Hybrid (VLM + tool) | Passage_Feasibility, Basketball_Shot | 65-69% |
| VLM-primary | Interaction_Direction, Knot_Type | 75-82% |

## 8 Tool Actions

| Action | What it does |
|--------|-------------|
| `track_colored_boxes` | Track colored bounding boxes across frames |
| `compensate_camera_motion` | Separate ego-motion from object motion |
| `estimate_camera_yaw` | Estimate cumulative camera rotation |
| `track_keypoints` | Track human pose keypoints (requires torch) |
| `optical_flow` | Dense/sparse optical flow between frames |
| `detect_blobs` | Detect colored blobs by HSV range |
| `frame_diff` | Compute frame differences for change detection |
| `visual_observation` | VLM-only analysis (no tool execution) |

## Setup

### 1. Install dependencies

```bash
pip install opencv-python numpy scipy
# Optional: pip install torch torchvision  (enables keypoint tracking)
```

### 2. Configure API keys

```bash
cp agent/llm_keys.example.json agent/llm_keys.local.json
chmod 600 agent/llm_keys.local.json
# Edit with your API gateway URL and keys
```

Or use environment variables:
```bash
export VISTR_LLM_BASE_URL="https://your-api-gateway/v1"
export VISTR_LLM_MODEL="your-model-name"
export VISTR_LLM_API_KEYS="key1,key2"
```

### 3. Prepare benchmark data

Download the ViSTR-Bench public split and place under `data/benchmarks/ViSTR-Bench-Public/`.

### 4. Run evaluation

```bash
python agent/coding_agent/eval_coding_agent.py
```

## Directory Structure

```
agent/
├── llm.py                      # LLM client (key rotation + retry)
├── prompts.py                  # Shared prompt templates
├── tools/                      # Low-level tool backends
│   ├── ground_track.py         # Color-based box tracking
│   ├── motion.py               # Optical flow analysis
│   ├── ego_odom.py             # Camera ego-motion estimation
│   ├── pose_motion.py          # Pose/keypoint extraction
│   └── ...
├── coding_agent/               # V4 model-driven pipeline
│   ├── pipeline.py             # Main orchestration
│   ├── action_executor.py      # 8 action handlers
│   ├── schemas.py              # EvidenceBundle dataclass
│   ├── sandbox.py              # Code execution sandbox
│   ├── prompts/                # Planner/Verifier prompts
│   ├── sdk/                    # Tool SDK (wraps tools/)
│   └── recipes/                # Pre-built analysis recipes
├── eval_*.py                   # Various evaluation scripts
configs/                        # Split definitions, baselines
docs/                           # Working logs, architecture decisions
scripts/                        # Utility scripts (visualization, web frontend)
```

## Reference

- Paper: [ViSTR-Bench: Visual Spatial-Temporal Reasoning Benchmark](https://arxiv.org/abs/2501.13253)
- Download the reference paper PDF separately (not included due to size)
