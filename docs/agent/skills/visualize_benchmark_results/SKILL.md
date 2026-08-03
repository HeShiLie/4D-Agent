---
status: active
scope: visualization
last_verified: 2026-08-01
owner: gaozhe
applies_to:
  - scripts/vistr_viewer.py
  - scripts/web_frontend.sh
  - visualize_results.py
  - scripts/visualize.sh
  - web/ (posters)
success_check:
  - "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8731/ | grep -q 200"
  - "ls data/visualizations/overview_dashboard.png"
  - "ffprobe data/visualizations/samples/<id>_replay.mp4 2>&1 | grep 'Video:'"
---

# Skill: Benchmark Results Visualization

两套前端，同一份 results JSONL：
- **Web 前端（交互，日常主力）**：`scripts/vistr_viewer.py`（**Streamlit**），端口 **8731**
- **静态渲染（离线/归档）**：`visualize_results.py`，出 overview PNG + 样本回放 MP4

## Web 前端（Streamlit）

```bash
# 启动（环境：/opt/conda/envs/python3.10.13/bin/python —— 与 48901 同款，streamlit/plotly/pandas/cv2 齐全）
bash scripts/web_frontend.sh                 # 默认 8731
bash scripts/web_frontend.sh 9000

# 后台常驻
nohup bash scripts/web_frontend.sh > /tmp/vistr_streamlit.log 2>&1 &

# 本地访问（服务器在远端时）
ssh -L 8731:localhost:8731 <此机器>
```

三个页面（侧边栏切换）：
- **Taxonomy**：总览指标 + 4 维度 × 15 任务卡片（海报图/题数/答案分布/来源），「🎲 看一题」→ 跳 Sample Browser 随机开一道该任务真题
- **Leaderboard**：Overall bars / By-Dimension / Per-Task Heatmap / Bias Monitor，内置论文参照行（Human 91.0 / GPT-5.4-thinking 62.0 / Chance-Freq 57.9），run 多选对比
- **Sample Browser**：run 下拉（含 `benchmark (ground truth)` 伪 run）、任务/对错/搜索过滤、样本列表单选、「🎲 换一题」；详情：`st.video` 播放、选项 GT/Pred 高亮、MATCH/MISMATCH、evidence/reasoning/Manual-CoT 折叠区

**视频为什么用 Streamlit 就稳**：`st.video(本地路径)` 由 Tornado 媒体端点服务，Range/keep-alive 开箱即用（与 48901 同机制）。教训：stdlib 手写视频服务即使升 HTTP/1.1 也不如直接用 Streamlit——已废弃 `web_frontend.py`（保留作参考，勿再用）。

## 静态渲染 quick start
```bash
# 冒烟测试（无需真实数据，生成 mock 结果并可视化）
bash scripts/visualize.sh --demo

# 常规：对 outputs/predictions/ 下全部 JSONL 出 overview dashboard
bash scripts/visualize.sh

# 指定结果文件 + 出错样本回放视频（case 分析主力用法）
bash scripts/visualize.sh --samples --results outputs/predictions/gpt54_direct_0731.jsonl

# 更多参数
/opt/conda/bin/python visualize_results.py --mode samples --only_wrong --max_samples 50 \
    --results outputs/predictions/xxx.jsonl
```

## Results JSONL schema（评测管线必须按此写结果）

每行一个样本：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | str | 样本 ID（与 benchmark 元数据一致） |
| `task` | str | 15 个子任务之一（拼写须与 `visualize_results.py:TASKS` 一致） |
| `dimension` | str | 4 维度之一（可推导，冗余存储） |
| `question` | str | 完整问题文本（含 Answer A or B） |
| `options` | [str, str] | 两个候选答案 |
| `gt` | str | ground truth（须等于 options 之一） |
| `pred` | str | 模型最终答案 |
| `correct` | bool | pred==gt 的判定结果 |
| `reasoning` | str | agent 推理文本（thinking 内容） |
| `evidence` | str | 工具证据的语言原生摘要 |
| `video` | str | 视频绝对路径；为空则回放用合成占位帧 |
| `model` | str | 模型/配置名（overview 图例用） |

命名约定：`<model>_<config>_<date>.jsonl`，如 `gpt54_direct_0731.jsonl`。
注意：`demo_results.jsonl` 是 mock 数据，正式 overview 前删除或用 `--results` 显式指定文件。

## Overview dashboard 布局（PNG）
```
┌──────────────────────────────────────────────────────────┐
│ Title: ViSTR-Bench Leaderboard Dashboard                  │
├──────────────┬───────────────────┬───────────────────────┤
│ A. Overall   │ B. By Dimension   │ C. Single-Option Bias │
│    acc bars  │    grouped bars   │    monitor (>90%偏置) │
│ vs GPT-5.4-  │ vs GPT-5.4-       │                       │
│ thinking /   │ thinking          │                       │
│ chance/human │                   │                       │
├──────────────┴───────────────────┴───────────────────────┤
│ D. Per-Task Heatmap: 我们的模型 + GPT-5.4-thinking +      │
│    Chance(Freq) + Human  × 15 子任务（按维度分组）         │
└──────────────────────────────────────────────────────────┘
```

参照值内置自论文 Table II（全集数字）：Human 91.0 / GPT-5.4-thinking 62.0 /
Chance(Frequency) 57.9 / Chance(Random) 50.0。榜单更新后改 `visualize_results.py:REFERENCE`。

## 样本回放视频布局（MP4, 1600×900）
```
┌─────────────────────────────────────────────────────┐
│ Header: ViSTR-Agent | id | task | Frame x/16        │
├──────────────────┬──────────────────────────────────┤
│ Video (uniform   │ Question + options (GT 高亮)     │
│  16 frames)      ├──────────────────────────────────┤
│                  │ Tool Evidence (语言原生摘要)      │
├──────────────────┼──────────────────────────────────┤
│ Agent Reasoning  │ GT: x | Pred: y | MATCH/MISMATCH │
└──────────────────┴──────────────────────────────────┘
```

## 颜色编码（沿用 0701 规范）
| 状态 | 颜色 |
|------|------|
| MATCH（预测正确） | 绿 (0,220,50) |
| MISMATCH（预测错误） | 红 (60,80,235) |
| GT 选项高亮 | 黄 (0,200,200) |
| 面板标题/强调 | 青 (80,200,250) |

## 编码规范
- ffmpeg libx264 + yuv420p（**禁用 OpenCV mp4v**，本机出花屏视频）
- 默认 16 帧均匀采样、fps=2（8 秒/样本）；真实视频缺失时渲染确定性合成占位帧

## CLI 参数
| 参数 | 默认 | 说明 |
|------|------|------|
| `--mode` | `all` | `overview` / `samples` / `all` |
| `--results` | predictions 下全部 | 指定 JSONL 文件（可多个） |
| `--max_samples` | 20 | 每次运行回放视频数上限 |
| `--only_wrong` | off | 只渲染预测错误样本（case 分析） |
| `--demo` | off | 生成 mock 结果（150 样本）并可视化 |
| `--vis_dir` | `data/visualizations` | 输出目录 |
