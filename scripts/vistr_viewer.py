#!/usr/bin/env python3
"""ViSTR-Bench Viewer — Streamlit 前端（Taxonomy / Leaderboard / Sample Browser）。

Usage:
    /opt/conda/envs/python3.10.13/bin/streamlit run scripts/vistr_viewer.py \
        --server.port 8731 --server.headless true
    # 远程代理：
    #   --server.baseUrlPath /notebook-xxx/proxy/8731/

数据：
  - benchmark GT: data/benchmarks/ViSTR-Bench-Public/data.json（伪 run，可直接看 670 题）
  - 预测结果:   outputs/predictions/*.jsonl（schema 见 docs/agent/skills/visualize_benchmark_results/SKILL.md）
"""

import json
import os
import random

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.join(PROJ_DIR, "data", "benchmarks", "ViSTR-Bench-Public")
PRED_DIR = os.path.join(PROJ_DIR, "outputs", "predictions")
PV_DIR = os.path.join(PROJ_DIR, "outputs", "plan_verify")
RATINGS_PATH = os.path.join(PV_DIR, "human_ratings.json")
POSTER_DIR = os.path.join(PROJ_DIR, "web", "posters")

TASKS = [
    "Vehicle Movement", "Relative Velocity", "Rotation Direction",
    "Ego Motion", "Passage Feasibility", "Interaction Direction",
    "Basketball Shot", "Soccer Shot", "Golf Shot", "Billiards Shot",
    "Swimming Race", "Fall Direction",
    "Jenga Stability", "Mikado Dependency", "Knot Type",
]
TASK_DIM = {
    "Vehicle Movement": "Motion Perception", "Relative Velocity": "Motion Perception",
    "Rotation Direction": "Motion Perception",
    "Ego Motion": "Spatial Relations", "Passage Feasibility": "Spatial Relations",
    "Interaction Direction": "Spatial Relations",
    "Basketball Shot": "Outcome Prediction", "Soccer Shot": "Outcome Prediction",
    "Golf Shot": "Outcome Prediction", "Billiards Shot": "Outcome Prediction",
    "Swimming Race": "Outcome Prediction", "Fall Direction": "Outcome Prediction",
    "Jenga Stability": "Physical Dynamics", "Mikado Dependency": "Physical Dynamics",
    "Knot Type": "Physical Dynamics",
}
DIMS = ["Motion Perception", "Spatial Relations", "Outcome Prediction",
        "Physical Dynamics"]
DIM_COLORS = {"Motion Perception": "#4fc3f7", "Spatial Relations": "#ffd54f",
              "Outcome Prediction": "#ef9a9a", "Physical Dynamics": "#81c784"}
# 论文全集参照（docs/knowledge/vistr_bench.md）
REFERENCE = {
    "Human": [90.6, 97.0, 100.0, 99.6, 85.5, 100.0, 81.5, 82.9,
              87.7, 77.3, 84.7, 100.0, 94.4, 98.8, 77.6],
    "GPT-5.4-thinking": [57.1, 75.0, 76.6, 75.6, 58.2, 87.5, 46.8, 51.3,
                         54.7, 58.7, 50.0, 56.5, 67.5, 47.0, 72.4],
    "Chance (Frequency)": [64.3, 59.5, 53.1, 53.4, 65.5, 83.9, 57.3, 52.5,
                           54.7, 53.3, 50.0, 58.7, 65.0, 54.2, 58.6],
}
REF_AVG = {"Human": 91.0, "GPT-5.4-thinking": 62.0, "Chance (Frequency)": 57.9}
BENCH_RUN = "__benchmark__"

st.set_page_config(page_title="ViSTR-Bench Viewer", layout="wide")


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
@st.cache_data
def load_benchmark():
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    out = []
    for r in rows:
        out.append({
            "id": f"bench_{r['id']}", "task": r["task"].replace("_", " "),
            "dimension": r["dimension"].replace("_", " "),
            "dataset": r.get("dataset", "?"),
            "question": r["direct_prompting"],
            "manual_cot": r.get("manual_cot_prompting", ""),
            "options": r["options"], "gt": r["answer"], "pred": "",
            "correct": None, "reasoning": "", "evidence": "",
            "video": r["video"], "model": "benchmark (ground truth)",
        })
    return out


@st.cache_data
def load_benchmark_index():
    """Return {id: sample} for enriching prediction runs with GT metadata."""
    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    return {r["id"]: r for r in rows}


@st.cache_data(ttl=30)
def load_run(path):
    samples = [json.loads(l) for l in open(path) if l.strip()]
    bench = load_benchmark_index()
    for s in samples:
        s["task"] = s["task"].replace("_", " ")
        if "evidence_summary" in s and "evidence" not in s:
            s["evidence"] = s["evidence_summary"]
        if "question" not in s or "video" not in s:
            ref = bench.get(s["id"], {})
            s.setdefault("question", ref.get("direct_prompting", ""))
            s.setdefault("options", ref.get("options", []))
            s.setdefault("video", ref.get("video", ""))
            s.setdefault("dimension", ref.get("dimension", "").replace("_", " "))
            s.setdefault("dataset", ref.get("dataset", "?"))
    return samples


def list_runs():
    runs = [{"id": BENCH_RUN, "model": "benchmark (ground truth)", "bench": True}]
    if os.path.isdir(PRED_DIR):
        for f in sorted(os.listdir(PRED_DIR)):
            if f.endswith(".jsonl"):
                runs.append({"id": f, "model": f[:-6], "bench": False})
    return runs


def get_samples(run_id):
    if run_id == BENCH_RUN:
        return load_benchmark()
    return load_run(os.path.join(PRED_DIR, run_id))


def acc_of(samples):
    scored = [s for s in samples if s.get("correct") is not None]
    if not scored:
        return None
    return 100.0 * sum(s["correct"] for s in scored) / len(scored)


# ---------------------------------------------------------------------------
# page: taxonomy
# ---------------------------------------------------------------------------
def _jump_to_case(task):
    """on_click 回调：跳 Sample Browser 并随机一题（回调里改 state 合法）。"""
    st.session_state.jump_task = task
    st.session_state.page = "Sample Browser"


def page_taxonomy():
    bench = load_benchmark()
    st.title("ViSTR-Bench Taxonomy（public 670 题）")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总题数", len(bench), "全集 1,340")
    c2.metric("维度", len(DIMS))
    c3.metric("子任务", len(TASKS))
    c4.metric("高确定工具覆盖", "~52% 题", help="见 docs/notes/analyses/2026-08-01_tool_design_analysis.md")

    for d in DIMS:
        d_tasks = [t for t in TASKS if TASK_DIM[t] == d]
        d_n = sum(1 for s in bench if s["dimension"] == d)
        st.markdown(
            f"<h3 style='color:{DIM_COLORS[d]};border-left:5px solid {DIM_COLORS[d]};"
            f"padding-left:10px'>{d} "
            f"<small style='color:#888'>{d_n} 题 · {100 * d_n / len(bench):.1f}%</small></h3>",
            unsafe_allow_html=True)
        cols = st.columns(len(d_tasks))
        for col, t in zip(cols, d_tasks):
            ts = [s for s in bench if s["task"] == t]
            with col:
                poster = os.path.join(POSTER_DIR, t.replace(" ", "_") + ".jpg")
                if os.path.exists(poster):
                    st.image(poster, use_container_width=True)
                st.markdown(f"**{t}** ({len(ts)})")
                ans = pd.Series([s["gt"] for s in ts]).value_counts()
                st.caption(" / ".join(f"{a}:{n}" for a, n in ans.items()))
                srcs = pd.Series([s["dataset"] for s in ts]).value_counts()
                st.caption("📦 " + " · ".join(f"{a}:{n}" for a, n in srcs.items()))
                if st.button("🎲 看一题", key=f"tax_{t}",
                             on_click=_jump_to_case, args=(t,)):
                    pass


# ---------------------------------------------------------------------------
# page: leaderboard
# ---------------------------------------------------------------------------
def page_leaderboard():
    st.title("Leaderboard（vs 论文参照）")
    runs = [r for r in list_runs() if not r["bench"]]
    if not runs:
        st.info("outputs/predictions/ 下还没有预测 JSONL。先跑 baseline 再回来。")
        return
    sel = st.sidebar.multiselect(
        "Runs", [r["id"] for r in runs], default=[r["id"] for r in runs],
        format_func=lambda rid: next(r["model"] for r in runs if r["id"] == rid))
    if not sel:
        st.warning("至少选一个 run")
        return

    stats = {}
    for rid in sel:
        ss = get_samples(rid)
        stats[rid] = {
            "overall": acc_of(ss), "n": len(ss),
            "per_task": {t: acc_of([s for s in ss if s["task"] == t]) for t in TASKS},
            "per_dim": {d: acc_of([s for s in ss if TASK_DIM.get(s["task"]) == d]) for d in DIMS},
        }

    # A. overall
    fig = go.Figure()
    names = [next(r["model"] for r in runs if r["id"] == rid) for rid in sel]
    fig.add_bar(x=names, y=[stats[r]["overall"] for r in sel], name="ours",
                marker_color="#4fc3f7", text=[f"{stats[r]['overall']:.1f}" for r in sel],
                textposition="outside")
    for k, v in REF_AVG.items():
        fig.add_hline(y=v, line_dash="dot", annotation_text=f"{k} {v}",
                      annotation_font_size=10)
    fig.update_layout(title="A. Overall Accuracy", yaxis_range=[0, 100],
                      height=340, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # B. per-dimension grouped
    fig = go.Figure()
    for rid, name in zip(sel, names):
        fig.add_bar(name=name, x=DIMS,
                    y=[stats[rid]["per_dim"][d] for d in DIMS])
    ref_dim = [float(np.mean([REFERENCE["GPT-5.4-thinking"][TASKS.index(t)]
                              for t in TASKS if TASK_DIM[t] == d])) for d in DIMS]
    fig.add_bar(name="GPT-5.4-thinking", x=DIMS, y=ref_dim, marker_color="#ffd54f")
    fig.update_layout(barmode="group", title="B. Accuracy by Dimension",
                      yaxis_range=[0, 100], height=360, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # C. per-task heatmap
    rows, z = [], []
    for rid, name in zip(sel, names):
        rows.append(name)
        z.append([stats[rid]["per_task"][t] if stats[rid]["per_task"][t] is not None
                  else np.nan for t in TASKS])
    for k in ["GPT-5.4-thinking", "Chance (Frequency)", "Human"]:
        rows.append(k)
        z.append(REFERENCE[k])
    fig = go.Figure(go.Heatmap(
        z=z, x=TASKS, y=rows, zmin=30, zmax=100, colorscale="RdYlGn",
        text=[["" if np.isnan(v) else f"{v:.0f}" for v in row] for row in z],
        texttemplate="%{text}", colorbar=dict(title="acc")))
    fig.update_layout(title="C. Per-Task Accuracy Heatmap", height=300 + 40 * len(rows),
                      margin=dict(t=40))
    st.plotly_chart(fig, use_container_width=True)

    # D. bias monitor
    st.subheader("D. Single-Option Bias Monitor")
    cols = st.columns(len(sel))
    for col, (rid, name) in zip(cols, zip(sel, names)):
        ss = get_samples(rid)
        n_bias, n_t = 0, 0
        for t in {s["task"] for s in ss}:
            preds = [s["pred"] for s in ss if s["task"] == t and s.get("pred")]
            if preds:
                n_t += 1
                if max(preds.count(v) for v in set(preds)) / len(preds) > 0.9:
                    n_bias += 1
        frac = 100.0 * n_bias / max(1, n_t)
        col.metric(name, f"{frac:.0f}% 任务偏置", f"{n_bias}/{n_t} tasks",
                   delta_color="inverse" if frac > 20 else "normal")


# ---------------------------------------------------------------------------
# page: sample browser
# ---------------------------------------------------------------------------
def _opt_md(o, gt, pred):
    mark = ""
    if o == gt and o == pred:
        mark = " ✅ GT=Pred"
    elif o == gt:
        mark = " 🎯 GT"
    elif pred and o == pred:
        mark = " 🔮 Pred"
    return f"- {'**' if (o == gt or o == pred) else ''}{o}{'**' if (o == gt or o == pred) else ''}{mark}"


def page_browser():
    runs = list_runs()
    st.title("Sample Browser")
    run_ids = [r["id"] for r in runs]
    run = st.sidebar.selectbox(
        "Run", run_ids, format_func=lambda rid: next(r["model"] for r in runs if r["id"] == rid))
    samples = get_samples(run)
    jump = st.session_state.get("jump_task")
    task_opts = ["（全部）"] + TASKS
    task = st.sidebar.selectbox(
        "任务", task_opts, index=task_opts.index(jump) if jump in TASKS else 0)
    status = st.sidebar.selectbox("对错", ["all", "correct", "wrong"])
    query = st.sidebar.text_input("搜索 id/问题", "")
    filtered = [s for s in samples
                if (task == "（全部）" or s["task"] == task)
                and (status == "all"
                     or (status == "correct" and s.get("correct") is True)
                     or (status == "wrong" and s.get("correct") is False))
                and (query.lower() in (s["id"] + s.get("question", "")).lower())]
    st.sidebar.markdown(f"**{len(filtered)} samples**")
    if not filtered:
        st.warning("无匹配样本")
        return

    options = [f"{'✅' if s['correct'] is True else '❌' if s['correct'] is False else '⬜'} "
               f"{s['id']}  [{s['task']}]" for s in filtered]
    # 选择状态：jump 或「换一题」时随机；切换任务/过滤时归零
    filt_key = (run, task, status, query)
    if st.session_state.get("filt_key") != filt_key or jump:
        st.session_state.filt_key = filt_key
        st.session_state.browser_idx = random.randrange(len(options)) \
            if jump else 0
        if jump:
            del st.session_state["jump_task"]

    def _reroll():
        st.session_state.browser_idx = random.randrange(len(options))

    st.sidebar.button("🎲 换一题", on_click=_reroll)
    idx = min(st.session_state.get("browser_idx", 0), len(options) - 1)
    sel = st.sidebar.radio("样本", options, index=idx)
    st.session_state.browser_idx = options.index(sel)
    s = filtered[options.index(sel)]

    col1, col2 = st.columns([3, 2])
    with col1:
        vpath = s.get("video") or ""
        if not os.path.isabs(vpath):
            vpath = os.path.join(BENCH_DIR, vpath)
        if vpath and os.path.exists(vpath):
            st.video(vpath)
        else:
            st.info("该样本无视频文件（demo 数据）")
        with st.expander("Manual CoT Prompt（官方模板）", expanded=False):
            st.code(s.get("manual_cot") or "N/A")
    with col2:
        st.subheader(s["id"])
        st.caption(f"{s['task']} · {s.get('dimension', '')} · 来源 {s.get('dataset', '?')}")
        st.markdown(f"**Q:** {s.get('question', '')}")
        st.markdown("**Options:**")
        for o in s.get("options", []):
            st.markdown(_opt_md(o, s.get("gt"), s.get("pred")))
        gt, pred = s.get("gt", "?"), s.get("pred", "")
        if s.get("correct") is True:
            st.success(f"GT: {gt}  |  Pred: {pred}  →  MATCH")
        elif s.get("correct") is False:
            st.error(f"GT: {gt}  |  Pred: {pred}  →  MISMATCH")
        else:
            st.info(f"GT: {gt}（ground truth 浏览模式）")
        if s.get("src"):
            src_label = {"recipe": "📋 Recipe (verified template)",
                         "generic": "🔧 Generic Solver (template-based)",
                         "codegen": "🤖 VLM CodeGen",
                         "vlm_direct": "👁️ VLM Observe+Judge (no tools)",
                         "recipe_fallback": "📋→🔧 Recipe Fallback",
                         "error": "💥 Error"}.get(s["src"], s["src"])
            elapsed = s.get("elapsed_s", 0)
            st.caption(f"Source: {src_label} · {elapsed:.1f}s")
        if s.get("analysis_spec"):
            with st.expander("🧭 Analysis Spec (Planner output)", expanded=False):
                if isinstance(s["analysis_spec"], dict):
                    spec = s["analysis_spec"]
                    if spec.get("entities"):
                        st.markdown(f"**Entities:** {', '.join(spec['entities'])}")
                    if spec.get("required_observations"):
                        st.markdown("**Observations:**")
                        for obs in spec["required_observations"]:
                            if isinstance(obs, dict):
                                st.markdown(f"- **{obs.get('what', '?')}** → `{obs.get('how', '?')}`")
                            else:
                                st.markdown(f"- {obs}")
                    if spec.get("comparison_logic"):
                        st.markdown(f"**Logic:** {spec['comparison_logic']}")
                    if spec.get("key_frames"):
                        st.markdown(f"**Key frames:** {spec['key_frames']}")
                else:
                    st.json(s["analysis_spec"])
        if s.get("code"):
            with st.expander("💻 Generated Code", expanded=False):
                st.code(s["code"], language="python")
        if s.get("evidence"):
            with st.expander("📊 Evidence", expanded=True):
                st.code(s["evidence"])
        if s.get("reasoning"):
            with st.expander("💭 Reasoning", expanded=True):
                st.code(s["reasoning"])
        if s.get("error"):
            with st.expander("⚠️ Error", expanded=True):
                st.code(s["error"])


# ---------------------------------------------------------------------------
# page: plan+verify（二阶段探究：模型怎么 plan / 怎么 verify）
# ---------------------------------------------------------------------------
TOOL_PATTERNS = {
    "目标检测/跟踪": ["检测", "跟踪", "YOLO", "ByteTrack", "MOT", "KLT", "SOT", "track"],
    "光流": ["光流", "optical flow"],
    "深度/3D 重建": ["深度", "3D", "三维", "重建", "点云", "标定", "透视校正", "VGGT", "反投影"],
    "人体姿态估计": ["姿态", "关键点", "pose", "骨架", "关节"],
    "轨迹/抛物线拟合": ["抛物线", "拟合", "轨迹外推", "parabola"],
    "局部放大": ["放大", "crop", "局部"],
    "时序/帧差分析": ["帧差", "时序", "差分", "光流幅值"],
}


@st.cache_data(ttl=10)
def load_plan_verify():
    """-> {filename: rows}（v1_partial 为旧盲 checklist prompt，v2 为证据验收 prompt）"""
    out = {}
    if not os.path.isdir(PV_DIR):
        return out
    for f in sorted(os.listdir(PV_DIR)):
        if not f.endswith(".jsonl"):
            continue
        rows = []
        for l in open(os.path.join(PV_DIR, f)):
            try:
                d = json.loads(l)
                if "error" not in d:
                    rows.append(d)
            except Exception:
                pass
        out[f] = rows
    return out


def load_ratings():
    try:
        return json.load(open(RATINGS_PATH))
    except Exception:
        return {}


def save_rating(sid, plan_score, verify_score, comment):
    import time as _time
    ratings = load_ratings()
    ratings[str(sid)] = {"plan": plan_score, "verify": verify_score,
                         "comment": comment,
                         "ts": _time.strftime("%Y-%m-%d %H:%M:%S")}
    tmp = RATINGS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(ratings, f, ensure_ascii=False, indent=1)
    os.replace(tmp, RATINGS_PATH)


def page_plan_verify():
    st.title("Plan + Verify 探究（qwen3-vl-plus，上下文隔离）")
    _pv_live_body()


@st.fragment(run_every=30)
def _pv_live_body():
    """30s 自动重跑：后台 runner 边跑边更新。"""
    by_file = load_plan_verify()
    if not by_file:
        st.info("outputs/plan_verify/ 还没有数据（后台任务可能刚启动，稍等刷新）")
        return
    files = list(by_file)
    default = [f for f in files if "v1_partial" not in f] or files
    sel_files = st.multiselect("数据源（prompt 版本）", files, default=default,
                               key="pv_files",
                               help="v1_partial=盲 checklist（旧）；无 v1 后缀=证据验收 v2（新）")
    rows = [r for f in sel_files for r in by_file[f]]
    n_done = len(rows)
    mtime = max((os.path.getmtime(os.path.join(PV_DIR, f))
                 for f in files), default=0)
    import time as _time
    running = (_time.time() - mtime) < 180
    if running:
        st.progress(min(n_done / 670, 1.0),
                    f"🏃 后台运行中：{n_done}/670 · 每 30s 自动刷新")
    else:
        st.caption(f"{'✅ 已完成' if n_done >= 670 else '⏸ 未在运行'} · {n_done}/670")
    if not rows:
        st.warning("所选数据源无数据")
        return

    # ---- aggregate ----
    plan_acc = 100 * sum(r["plan"]["correct"] for r in rows) / len(rows)
    ver_acc = 100 * sum(r["verify"]["correct"] for r in rows) / len(rows)
    agree = 100 * sum(r["agree"] for r in rows) / len(rows)
    both_right = 100 * sum(r["plan"]["correct"] and r["verify"]["correct"]
                           for r in rows) / len(rows)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plan 准确率", f"{plan_acc:.1f}%")
    c2.metric("Verify 准确率", f"{ver_acc:.1f}%")
    c3.metric("Plan↔Verify 一致率", f"{agree:.1f}%")
    c4.metric("双对率", f"{both_right:.1f}%")
    ratings = load_ratings()
    if ratings:
        mp = sum(v["plan"] for v in ratings.values()) / len(ratings)
        mv = sum(v["verify"] for v in ratings.values()) / len(ratings)
        st.caption(f"🧑‍🏫 已人工点评 {len(ratings)} 题 · Plan 均分 {mp:.1f}/5 · Verify 均分 {mv:.1f}/5")

    # per-task table
    st.subheader("分任务统计")
    tbl = []
    for t in TASKS:
        ts = [r for r in rows if r["task"] == t]
        if not ts:
            continue
        tbl.append({
            "任务": t, "n": len(ts),
            "plan_acc": round(100 * sum(r["plan"]["correct"] for r in ts) / len(ts), 1),
            "verify_acc": round(100 * sum(r["verify"]["correct"] for r in ts) / len(ts), 1),
            "agree%": round(100 * sum(r["agree"] for r in ts) / len(ts), 1),
        })
    st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

    # tool frequency from plan texts
    st.subheader("模型想要的工具（plan 文本词频，按题计数）")
    counts = {k: 0 for k in TOOL_PATTERNS}
    for r in rows:
        text = r["plan"].get("plan_text", "") or r["plan"].get("raw", "")
        for k, kws in TOOL_PATTERNS.items():
            if any(kw.lower() in text.lower() for kw in kws):
                counts[k] += 1
    fig = go.Figure(go.Bar(
        x=list(counts), y=list(counts.values()),
        text=list(counts.values()), textposition="outside",
        marker_color="#4fc3f7"))
    fig.update_layout(height=300, margin=dict(t=20, b=20),
                      yaxis_title="提及题数（/{}）".format(len(rows)))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---- per-sample ----
    st.subheader("逐样本查看")
    f1, f2, f3 = st.columns([2, 2, 1])
    task_sel = f1.selectbox("任务", ["（全部）"] + TASKS, key="pv_task")
    flag_sel = f2.selectbox("筛选", ["all", "both_wrong", "disagree"], key="pv_flag")
    newest = f3.checkbox("最新优先", value=True, key="pv_newest")
    filt = [r for r in rows if task_sel == "（全部）" or r["task"] == task_sel]
    if flag_sel == "both_wrong":
        filt = [r for r in filt if not r["plan"]["correct"] and not r["verify"]["correct"]]
    elif flag_sel == "disagree":
        filt = [r for r in filt if not r["agree"]]
    if newest:
        filt = filt[::-1]
    st.caption(f"{len(filt)} 条")
    if not filt:
        st.warning("无匹配")
        return
    ids = [r["id"] for r in filt]
    sid = st.selectbox("样本", ids,
                       format_func=lambda i: f"#{i} [{filt[ids.index(i)]['task']}] "
                                             f"gt={filt[ids.index(i)]['gt']} "
                                             f"plan={'✅' if filt[ids.index(i)]['plan']['correct'] else '❌'}/"
                                             f"verify={'✅' if filt[ids.index(i)]['verify']['correct'] else '❌'}"
                                             f"{' 🧑‍🏫' if str(i) in ratings else ''}",
                       key="pv_id")
    r = filt[ids.index(sid)]

    vpath = os.path.join(BENCH_DIR, r["video"])
    if os.path.exists(vpath):
        st.video(vpath)
    st.markdown(f"**Q:** {r['question']}　**GT: {r['gt']}**")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"### 🧭 Plan {'✅' if r['plan']['correct'] else '❌'}")
        st.markdown(r["plan"].get("plan_text") or r["plan"]["raw"])
        st.info(f"答案: {r['plan']['answer']} · 置信度 {r['plan']['confidence']}")
    with c2:
        st.markdown(f"### ✅ Verify {'✅' if r['verify']['correct'] else '❌'}")
        is_v2 = bool(r["verify"].get("criteria"))
        st.markdown(f"**{'Acceptance Criteria（验收标准+反欺骗）' if is_v2 else 'Checklist'}**")
        st.markdown(r["verify"].get("criteria") or r["verify"].get("checklist", ""))
        with st.expander("self_check 逐条结果"):
            st.markdown(r["verify"].get("self_check", ""))
        st.info(f"答案: {r['verify']['answer']} · 置信度 {r['verify']['confidence']}")

    # ---- 人工点评 ----
    st.divider()
    st.markdown("### 🧑‍🏫 人工点评")
    cur = ratings.get(str(sid), {})
    rc1, rc2 = st.columns(2)
    p_score = rc1.radio("Plan 质量", [1, 2, 3, 4, 5],
                        index=cur.get("plan", 3) - 1, horizontal=True,
                        format_func=lambda x: "⭐" * x, key=f"rate_p_{sid}")
    v_score = rc2.radio("Verify 质量", [1, 2, 3, 4, 5],
                        index=cur.get("verify", 3) - 1, horizontal=True,
                        format_func=lambda x: "⭐" * x, key=f"rate_v_{sid}")
    comment = st.text_area(
        "点评（plan 哪里不靠谱 / checklist 漏了什么 / 工具设想是否可行）",
        value=cur.get("comment", ""), height=80, key=f"rate_c_{sid}")
    if cur:
        st.caption(f"上次点评于 {cur.get('ts', '?')}")
    if st.button("💾 保存点评", key=f"rate_save_{sid}"):
        save_rating(sid, p_score, v_score, comment)
        st.toast(f"已保存 #{sid} 的点评", icon="💾")


# ---------------------------------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "Taxonomy"
page = st.sidebar.radio("页面",
                        ["Taxonomy", "Leaderboard", "Sample Browser", "Plan+Verify"],
                        key="page")
if page == "Taxonomy":
    page_taxonomy()
elif page == "Leaderboard":
    page_leaderboard()
elif page == "Plan+Verify":
    page_plan_verify()
else:
    page_browser()
