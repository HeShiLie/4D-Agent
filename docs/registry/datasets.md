---
status: active
scope: general
last_verified: 2026-08-01
owner: gaozhe
---

# Dataset Registry

Index of all datasets and data sources used in this project.

## Format

```markdown
### Dataset Name
**Path**: `/absolute/path/or/relative`
**Format**: Description of file structure
**Size**: Approximate (files/GB)
**Used by**: Which scripts consume this
**Notes**: Access restrictions, versioning, etc.
```

---

### ViSTR-Bench (public split)
**Path**: `data/benchmarks/ViSTR-Bench-Public/` → 软链至 `/mnt/xlab-nas-wm/gaozhe.gz/hf_datasets/ViSTR-Bench-Public/`
**Format**: `data.json`（670 条：id / dataset / dimension / task / **direct_prompting** / **manual_cot_prompting** / video 相对路径 / answer / options）+ `data/<Dimension>/<Task>/<Dataset>/*.mp4`
**Size**: 670 QA pairs，2.7GB，视频已校验 0 缺失（h264，典型 1920×1080@30fps，数秒级片段）
**Used by**: agent 评测管线（规划中）、`visualize_results.py`
**Notes**: 任务/维度名为下划线格式（如 `Basketball_Shot` / `Outcome_Prediction`）；每题自带官方 Manual CoT 模板；public split 的 Chance(Frequency)=**52.7%**（全集 57.9%）；私有 held-out 集禁止调参。详见 `docs/knowledge/vistr_bench.md`

### ViSTR-Bench paper
**Path**: `references/ViSTR-Bench.pdf`
**Format**: 37 页 arXiv 论文（2607.20868）
**Used by**: 知识文档 `docs/knowledge/vistr_bench.md` 的来源
**Notes**: Appendix B 含全部 15 个 direct-prompting 模板与 Manual CoT 模板
