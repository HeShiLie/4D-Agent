---
status: completed
date: 2026-07-31
scope: visualization
plan: docs/working_logs/plans/active/2026-07-31-vistr-agent-v1.md
---

# Run: 可视化前端冒烟测试（demo 数据）

## Configuration

| Parameter | Value |
|-----------|-------|
| Script | `visualize_results.py`（经 `scripts/visualize.sh`） |
| Input | mock 结果 `outputs/predictions/demo_results.jsonl`（150 样本 / 15 任务 × 10） |
| Output | `data/visualizations/overview_dashboard.png` + `samples/*_replay.mp4` |
| Python | `/opt/conda/bin/python`（cv2 5.0.0 / mpl 3.10.9 / np 2.2.6，本次补装 opencv-headless + matplotlib） |

## Command

```bash
/opt/conda/bin/python -u visualize_results.py --demo --max_samples 2
ffprobe -v error -show_entries stream=codec_name,width,height,nb_frames \
  data/visualizations/samples/vehicle_movement_0000_replay.mp4
```

## Result

成功。

- overview PNG：4 面板齐全（Overall bars / By-Dimension / Bias Monitor / 15 任务热力图），
  参照行（Human 91.0 / GPT-5.4-thinking 62.0 / Chance-Freq 57.9）渲染正确，行标签不截断，
  深底单元格数字可读（初版两个问题——y 标签截断、深底数字不可读——已修复并复验）。
- 回放 MP4：codec=h264, 1600×900, 16 帧；抽帧目检确认 5 区块布局
  （Header/Video/Question+GT 高亮/Evidence/Reasoning/Verdict-MATCH 绿色）正确。

## Artifacts

- `data/visualizations/overview_dashboard.png`
- `data/visualizations/samples/vehicle_movement_000{0,1}_replay.mp4`
- `outputs/predictions/demo_results.jsonl`（mock，正式评测前删除或忽略）

## Notes

- 编码走 ffmpeg libx264（OpenCV mp4v 在本机会花屏，沿用 0701 规范）。
- 真实视频缺失时回放自动用确定性合成占位帧，保证前端在数据下载前始终可冒烟。
