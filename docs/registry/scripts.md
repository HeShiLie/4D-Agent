---
status: active
scope: general
last_verified: 2026-08-01
owner: gaozhe
---

# Script Registry

Index of all scripts in this project. Each entry documents purpose, usage, inputs, and outputs.

## Format

```markdown
### path/to/script.sh
**Purpose**: One-line description.
**Usage**: `command to run`
**Inputs**: What it reads
**Outputs**: What it produces
**Notes**: Any caveats
```

---

## Agent 包（`agent/`）

### agent/run_plan_verify.py
**Purpose**: 二阶段探究 runner——qwen3-vl-plus 对每题做 plan + verify 双隔离调用
**Usage**: `/opt/conda/bin/python -u agent/run_plan_verify.py [--limit N] [--workers 8] [--task Basketball_Shot]`
**Inputs**: benchmark `data.json` + 视频（16 帧均匀抽样 base64）；`agent/llm_keys.local.json`（chmod 600，双 key）
**Outputs**: `outputs/plan_verify/qwen3-vl-plus_plan_verify.jsonl`（断点续跑，按 id 跳过）
**Notes**: PLAN/VERIFY 为独立会话（无共享历史）；各产出 plan文本/checklist/answer/confidence

### agent/llm.py
**Purpose**: AMAP 网关 OpenAI 兼容客户端（urllib 零依赖；key 轮换；429/5xx 指数退避）
**Notes**: keys 只存 `agent/llm_keys.local.json`，勿写入任何文档

### agent/prompts.py
**Purpose**: PLAN/VERIFY prompt 模板 + 消息组装（文本+16 帧图像）

## Root-level Python

### visualize_results.py
**Purpose**: ViSTR-Bench 可视化前端 — leaderboard 总览 dashboard（PNG）+ 样本级回放视频（MP4）
**Usage**: `/opt/conda/bin/python visualize_results.py [--mode overview|samples] [--results outputs/predictions/xxx.jsonl]`
**Inputs**: `outputs/predictions/*.jsonl`（每行一个样本：id/task/question/options/gt/pred/reasoning/video 等）
**Outputs**: `data/visualizations/overview_dashboard.png`、`data/visualizations/samples/<id>_replay.mp4`
**Notes**: 内置 `--demo` 生成 mock 数据用于冒烟；详见 `docs/agent/skills/visualize_benchmark_results/SKILL.md`

### web_frontend.py（已废弃）
**Status**: DEPRECATED 2026-08-01 — stdlib 手写视频服务在浏览器下播放不稳，被 Streamlit 方案取代。文件保留仅作参考，勿再启动。
**替代**: `scripts/vistr_viewer.py`

### scripts/vistr_viewer.py
**Purpose**: Web 可视化前端（Streamlit）— Taxonomy / Leaderboard / Sample Browser 三页
**Usage**: `/opt/conda/envs/python3.10.13/bin/python -m streamlit run scripts/vistr_viewer.py --server.port 8731 --server.headless true`（或 `bash scripts/web_frontend.sh`）
**Inputs**: benchmark `data.json` + `outputs/predictions/*.jsonl` + `web/posters/`
**Outputs**: HTTP 服务于 8731
**Notes**: `st.video(本地路径)` 播视频（与 48901 同机制）；跳转用 on_click 回调改 session_state（widget 实例化后不可改）
**Code Map**: [`docs/code_maps/scripts/vistr_viewer.md`](../code_maps/scripts/vistr_viewer.md)

## Shell Scripts (`scripts/`)

### scripts/visualize.sh
**Purpose**: visualize_results.py 的封装（固定 python 路径与输出目录）
**Usage**: `bash scripts/visualize.sh [--samples <results.jsonl>] [--demo]`
**Inputs**: 同 visualize_results.py
**Outputs**: `data/visualizations/`
**Notes**: `set -e`；编码走 ffmpeg libx264（禁用 OpenCV mp4v）

### scripts/web_frontend.sh
**Purpose**: Streamlit 前端启动器（环境 `/opt/conda/envs/python3.10.13/bin/python`，与 48901 同款）
**Usage**: `bash scripts/web_frontend.sh [端口, 默认 8731]`；后台用 `nohup ... &`
**Outputs**: HTTP 服务（8731 端口）
**Notes**: 远端访问用 `ssh -L 8731:localhost:8731 <host>`

### scripts/extract_case_frames.py
**Purpose**: 逐 case 审查抽帧——每视频 4 帧拼 2×2 拼图（省 token），生成分层抽样 worklist
**Usage**: `/opt/conda/bin/python scripts/extract_case_frames.py [--n_per_task 5] [--seed 7]`
**Inputs**: benchmark `data.json` + 视频
**Outputs**: `docs/notes/analyses/2026-08-01_case_review/{worklist.json, frames/*.jpg}`
**Notes**: 抽样按答案类别分层+来源多样优先

### scripts/case_log_append.py
**Purpose**: 向 case_log.jsonl 追加结构化观察记录（stdin 收 JSON 数组）
**Usage**: `cat <<'JSON' | /opt/conda/bin/python scripts/case_log_append.py ... JSON`
**Outputs**: `docs/notes/analyses/2026-08-01_case_review/case_log.jsonl`

### scripts/gen_task_posters.py
**Purpose**: 为 taxonomy 页生成每任务代表帧海报（15 张）
**Usage**: `/opt/conda/bin/python scripts/gen_task_posters.py`
**Inputs**: benchmark `data.json` + 每任务首个视频
**Outputs**: `web/posters/<Task_Name>.jpg`（480×270）
