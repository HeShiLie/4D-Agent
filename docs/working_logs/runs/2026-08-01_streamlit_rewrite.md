---
status: completed
date: 2026-08-01
scope: visualization
plan: docs/working_logs/plans/active/2026-07-31-vistr-agent-v1.md
---

# Run: Web 前端重做（stdlib → Streamlit）— 视频播放根治

## 背景

用户反馈 8731 页面视频仍无法播放，而 48901 的前端能正常播。排查确认 48901 为
Streamlit 应用（`st.video` 由 Tornado 媒体端点服务，Range/keep-alive 开箱即用），
运行环境 `/opt/conda/envs/python3.10.13`（streamlit 1.60 / plotly 6.9 / pandas 2.3.3 / cv2 5.0）。

决策：放弃手写 stdlib 视频服务（HTTP/1.1 修复后仍不可靠），用同款环境重写为 Streamlit。

## 交付

- `scripts/vistr_viewer.py`：三页
  - Taxonomy：指标卡 + 4 维度 × 15 任务卡片（海报/题数/答案分布/来源），「看一题」跳浏览器随机真题
  - Leaderboard：plotly Overall bars / By-Dimension / Per-Task Heatmap / Bias Monitor + 论文参照行
  - Sample Browser：run/任务/对错/搜索过滤 + 样本单选 + 换一题 + st.video + GT/Pred 高亮 + 三折叠区
- `scripts/web_frontend.sh`：改为 streamlit 启动器
- `web_frontend.py`：标记 DEPRECATED（保留参考）

## Command / Verification（AppTest 无头冒烟）

```bash
/opt/conda/envs/python3.10.13/bin/python - <<'EOF'
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("scripts/vistr_viewer.py"); at.run()
# Taxonomy: 0 异常, 4 metrics, 15 卡片按钮; 点击 -> page=Sample Browser, 0 异常
# Leaderboard: 0 异常, 3 plotly charts
# Sample Browser: 0 异常
EOF
nohup bash scripts/web_frontend.sh > /tmp/vistr_streamlit.log 2>&1 &
```

## Result

- 三页 AppTest 全部 0 异常（含 taxonomy→browser 跳转链路）
- 服务运行中 `http://<host>:8731`（python pid 监听 8731，index 200）
- 视频播放机制与 48901 完全一致（st.video 本地路径）

## Notes（经验）

- Streamlit 里改 widget 的 session_state 必须在 `on_click` 回调中（widget 实例化后同 run 内不可改）
- `use_container_width` 在 1.60 起弃用警告（仍可用；后续换 `width='stretch'`）
