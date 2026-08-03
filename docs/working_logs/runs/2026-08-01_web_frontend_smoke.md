---
status: completed
date: 2026-08-01
scope: visualization
plan: docs/working_logs/plans/active/2026-07-31-vistr-agent-v1.md
---

# Run: Web 可视化前端冒烟测试（端口 8731）

## Configuration

| Parameter | Value |
|-----------|-------|
| Script | `web_frontend.py`（stdlib 零依赖；`scripts/web_frontend.sh` 封装） |
| Input | benchmark `data.json`（670 题伪 run）+ `outputs/predictions/demo_results.jsonl` |
| Output | HTTP 服务 `0.0.0.0:8731`（静态页 `web/`） |
| Python | `/opt/conda/bin/python`（无第三方依赖；flask 环境损坏故用 stdlib） |

## Command

```bash
nohup /opt/conda/bin/python -u web_frontend.py --port 8731 > /tmp/vistr_web.log 2>&1 &
curl -s http://127.0.0.1:8731/api/runs
curl -s "http://127.0.0.1:8731/api/overview?run=demo_results.jsonl"
curl -s "http://127.0.0.1:8731/api/samples?run=__benchmark__&task=Basketball%20Shot"
curl -s -H "Range: bytes=0-1023" \
  "http://127.0.0.1:8731/video/@ext/data/Outcome_Prediction/Basketball_Shot/Ego4D/775acd8e-...mp4"
node --check web/app.js
```

## Result

成功。

- `/api/runs`：benchmark GT（670）+ demo（150）两个 run 正确列出
- `/api/overview`：overall 54.0、per-task/per-dim/bias 聚合正确，model 字段已补（初版漏返回已修复）
- `/api/samples` 过滤：Basketball Shot 62 条，与 data.json 一致
- `/api/sample`：video_url 正确映射到 `/video/@ext/...`
- 视频流：Range 请求返回 206 且字节数精确（1024B / 1MB），HTML5 可拖动
- 安全：路径穿越 `..%2F..%2Fetc%2Fpasswd` → 404；未知 run → 404
- `node --check web/app.js` 语法通过（机器无头浏览器，未做截图级验证）

## Artifacts

- 服务进程：`web_frontend.py --port 8731`（nohup，日志 `/tmp/vistr_web.log`）
- 页面：`http://<host>:8731/`（远端访问 `ssh -L 8731:localhost:8731 <host>`）

## Notes

- 环境 flask 缺 werkzeug/click 且依赖链破损，故服务端用纯 stdlib 实现，零部署风险。
- benchmark 作为伪 run（`__benchmark__`）接入样本浏览器，baseline 未跑前即可人工过数据。
