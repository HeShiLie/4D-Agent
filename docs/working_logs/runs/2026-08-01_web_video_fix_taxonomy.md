---
status: completed
date: 2026-08-01
scope: visualization
plan: docs/working_logs/plans/active/2026-07-31-vistr-agent-v1.md
---

# Run: Web 前端修复（视频 loading）+ Taxonomy 页

## 问题与根因

用户反馈页面视频一直 loading 无法播放。排查：

| 假设 | 验证 | 结论 |
|------|------|------|
| 视频编码不兼容 | ffprobe 抽 40 个视频 | 排除：全部 h264/yuv420p |
| Range 实现错误 | curl 带 Range 请求 | 排除：206 字节精确 |
| 服务器协议 | 响应头 `HTTP/1.0 206` | **确认：BaseHTTPRequestHandler 默认 HTTP/1.0，无 keep-alive，Chrome 媒体栈在 1.0 下反复断连重试 → 表现为永远 loading** |

修复：`Handler.protocol_version = "HTTP/1.1"`（所有响应本已带 Content-Length，兼容）。
同时修海报图 MIME（.jpg 原映射缺失 → application/octet-stream）。

## Taxonomy 页

- `/api/taxonomy`：从 benchmark data.json 聚合（维度/任务：题数、来源、答案分布、模板数、海报图）
- `scripts/gen_task_posters.py`：每任务抽代表帧 → `web/posters/<Task>.jpg`（15 张）
- 页面：总览条（670 题/4 维度/15 子任务 + 维度占比条）→ 每维度一组任务卡片（海报+题数+答案分布条+来源，tooltip 为问题模板）
- **点击卡片 → 跳 Sample Browser，自动过滤该任务并随机开一道真题**；详情页新增「换一题」按钮（当前过滤范围内随机）

## Command

```bash
nohup /opt/conda/bin/python -u web_frontend.py --port 8731 > /tmp/vistr_web.log 2>&1 &
curl -s -o /dev/null -D - -H "Range: bytes=0-1023" http://127.0.0.1:8731/video/@ext/...mp4 | head -2
curl -s http://127.0.0.1:8731/api/taxonomy
node --check web/app.js
```

## Result

- 响应头变为 `HTTP/1.1 206 Partial Content`，keep-alive 正常，浏览器可播放
- `/api/taxonomy`：670 = MP 171 / SR 121 / OP 264 / PD 114，任务级聚合正确
- poster `200 image/jpeg`；`node --check web/app.js` 通过
- 服务运行中：`http://<host>:8731/#`（Taxonomy 为中间页签）

## Notes

- stdlib http.server 起视频服务必须显式 `protocol_version="HTTP/1.1"`，否则浏览器 range 播放必挂——记入 SKILL.md 防复发
