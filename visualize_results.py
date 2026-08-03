"""
ViSTR-Bench Results Visualization — overview dashboard + per-sample replay videos.

Layout conventions follow docs_gaozhe/agent/skills/visualize_pose_outputs (0701 project):
  - OpenCV panels + matplotlib charts, warm dark background
  - MATCH/MISMATCH color coding (green/red)
  - mp4 via ffmpeg libx264 (never OpenCV mp4v)

Modes:
  overview  Leaderboard-style dashboard PNG from results JSONL files
            (our models vs paper reference rows: Human / GPT-5.4-thinking / chance levels).
  samples   Per-sample replay MP4s: video frames + question/options + reasoning/evidence
            + GT vs Pred MATCH/MISMATCH footer.
  --demo    Write a mock results JSONL (and synthetic frames when no video file exists)
            so the whole frontend is smoke-testable without benchmark data.

Results JSONL schema (one sample per line):
  {id, task, dimension, question, options:[A,B], gt, pred, correct,
   reasoning, evidence, video (abs path or ""), model}
"""
import argparse
import json
import os
import subprocess
import tempfile

import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROJ_DIR = "/mnt/xlab-nas-wm/gaozhe.gz/codes/PlayGround/0731-spatial_temperal_agent"
PRED_DIR = os.path.join(PROJ_DIR, "outputs", "predictions")
VIS_DIR = os.path.join(PROJ_DIR, "data", "visualizations")
os.makedirs(VIS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Benchmark constants (paper Table II, full-set numbers; see docs/knowledge/vistr_bench.md)
# ---------------------------------------------------------------------------
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
DIMS = ["Motion Perception", "Spatial Relations", "Outcome Prediction", "Physical Dynamics"]
DIM_SHORT = {"Motion Perception": "Moti.\nPerc.", "Spatial Relations": "Spat.\nRela.",
             "Outcome Prediction": "Outc.\nPred.", "Physical Dynamics": "Phys.\nDyna."}

# Reference rows: (avg, per-task acc list in TASKS order)
REFERENCE = {
    "Human": (91.0, [90.6, 97.0, 100.0, 99.6, 85.5, 100.0, 81.5, 82.9,
                     87.7, 77.3, 84.7, 100.0, 94.4, 98.8, 77.6]),
    "GPT-5.4-thinking": (62.0, [57.1, 75.0, 76.6, 75.6, 58.2, 87.5, 46.8, 51.3,
                                54.7, 58.7, 50.0, 56.5, 67.5, 47.0, 72.4]),
    "Chance (Frequency)": (57.9, [64.3, 59.5, 53.1, 53.4, 65.5, 83.9, 57.3, 52.5,
                                  54.7, 53.3, 50.0, 58.7, 65.0, 54.2, 58.6]),
    "Chance (Random)": (50.0, [50.0] * 15),
}

# ---------------------------------------------------------------------------
# Colors (BGR for cv2) — 0701 palette
# ---------------------------------------------------------------------------
COLOR_BG = (87, 64, 46)
COLOR_PANEL = (70, 52, 38)
COLOR_PANEL_EDGE = (90, 90, 90)
COLOR_MATCH = (0, 220, 50)
COLOR_MISMATCH = (60, 80, 235)
COLOR_TEXT = (240, 240, 240)
COLOR_TEXT_DIM = (180, 180, 180)
COLOR_ACCENT = (80, 200, 250)
COLOR_GT = (0, 200, 200)
MPL_BG = "#2e4057"      # matches COLOR_BG-ish tone for charts
MPL_PANEL = "#3d3327"

FONT = cv2.FONT_HERSHEY_SIMPLEX


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_results(paths):
    """Load results JSONL files -> {model_name: [samples]}"""
    runs = {}
    for p in paths:
        samples = []
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
        if not samples:
            continue
        model = samples[0].get("model") or os.path.splitext(os.path.basename(p))[0]
        runs[model] = samples
    return runs


def per_task_acc(samples):
    """-> {task: acc%} over TASKS (tasks absent from data are omitted)."""
    out = {}
    for t in TASKS:
        ss = [s for s in samples if s["task"] == t]
        if ss:
            out[t] = 100.0 * sum(1 for s in ss if s.get("correct")) / len(ss)
    return out


def overall_acc(samples):
    return 100.0 * sum(1 for s in samples if s.get("correct")) / max(1, len(samples))


def dim_acc(samples):
    out = {}
    for d in DIMS:
        ss = [s for s in samples if TASK_DIM.get(s["task"]) == d]
        if ss:
            out[d] = 100.0 * sum(1 for s in ss if s.get("correct")) / len(ss)
    return out


# ---------------------------------------------------------------------------
# Overview dashboard (matplotlib -> PNG)
# ---------------------------------------------------------------------------
def _style_ax(ax):
    ax.set_facecolor(MPL_PANEL)
    for spine in ax.spines.values():
        spine.set_color("#888888")
    ax.tick_params(colors="#dddddd", labelsize=8)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color("#dddddd")
    ax.title.set_color("#f0f0f0")


def render_overview(runs, out_path):
    models = list(runs.keys())
    n_models = len(models)

    fig = plt.figure(figsize=(22, 13), facecolor=MPL_BG)
    fig.suptitle("ViSTR-Bench Leaderboard Dashboard", fontsize=20, color="#f0f0f0",
                 fontweight="bold", y=0.985)
    subtitle = (f"models: {', '.join(models)}   |   "
                f"samples: {sum(len(v) for v in runs.values())}   |   "
                f"reference: paper Table II (full set)")
    fig.text(0.5, 0.955, subtitle, ha="center", fontsize=11, color="#bbbbbb")

    gs = fig.add_gridspec(2, 3, left=0.075, right=0.97, top=0.90, bottom=0.08,
                          hspace=0.55, wspace=0.30)

    # --- Panel A: overall accuracy bars ------------------------------------------------
    axA = fig.add_subplot(gs[0, 0])
    names = models + ["GPT-5.4\n-thinking", "Chance\n(Freq)", "Human"]
    ours = [overall_acc(runs[m]) for m in models]
    vals = ours + [62.0, 57.9, 91.0]
    colors = (["#4fc3f7"] * n_models) + ["#ffd54f", "#9e9e9e", "#81c784"]
    bars = axA.bar(range(len(names)), vals, color=colors)
    for b, v in zip(bars, vals):
        axA.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}",
                 ha="center", fontsize=9, color="#f0f0f0")
    axA.axhline(57.9, color="#9e9e9e", ls="--", lw=1, alpha=0.7)
    axA.set_xticks(range(len(names)))
    axA.set_xticklabels(names, rotation=20, ha="right")
    axA.set_ylim(0, 100)
    axA.set_ylabel("Accuracy (%)", color="#dddddd")
    axA.set_title("A. Overall Accuracy vs References", fontsize=12)
    _style_ax(axA)

    # --- Panel B: per-dimension grouped bars -------------------------------------------
    axB = fig.add_subplot(gs[0, 1])
    width = 0.8 / (n_models + 1)
    ref_dims = {d: float(np.mean([REFERENCE["GPT-5.4-thinking"][1][TASKS.index(t)]
                                  for t in TASKS if TASK_DIM[t] == d])) for d in DIMS}
    for i, m in enumerate(models):
        da = dim_acc(runs[m])
        xs = np.arange(len(DIMS)) + i * width
        axB.bar(xs, [da.get(d, 0) for d in DIMS], width=width, label=m, color="#4fc3f7"
                if i == 0 else None)
    xs = np.arange(len(DIMS)) + n_models * width
    axB.bar(xs, [ref_dims[d] for d in DIMS], width=width, label="GPT-5.4-thinking",
            color="#ffd54f")
    axB.set_xticks(np.arange(len(DIMS)) + 0.4)
    axB.set_xticklabels([DIM_SHORT[d] for d in DIMS])
    axB.set_ylim(0, 100)
    axB.set_title("B. Accuracy by Dimension", fontsize=12)
    axB.legend(fontsize=7, facecolor=MPL_PANEL, labelcolor="#dddddd")
    _style_ax(axB)

    # --- Panel C: prediction-distribution / single-option-bias monitor ------------------
    axC = fig.add_subplot(gs[0, 2])
    # fraction of tasks where one option is predicted >90% of the time (bias indicator)
    bias_frac, tot_pred = [], []
    for m in models:
        n_bias = 0
        tasks_seen = set(s["task"] for s in runs[m])
        for t in tasks_seen:
            ss = [s for s in runs[m] if s["task"] == t]
            if not ss:
                continue
            top = max(ss.count(s) for s in {x["pred"] for x in ss}) if ss else 0
            preds = [s["pred"] for s in ss]
            top = max(preds.count(v) for v in set(preds))
            if top / len(preds) > 0.9:
                n_bias += 1
        bias_frac.append(100.0 * n_bias / max(1, len(tasks_seen)))
        tot_pred.append(len(runs[m]))
    bars = axC.bar(models, bias_frac, color="#ef9a9a")
    for b, v, n in zip(bars, bias_frac, tot_pred):
        axC.text(b.get_x() + b.get_width() / 2, v + 1.5,
                 f"{v:.0f}%\n(n={n})", ha="center", fontsize=8, color="#f0f0f0")
    axC.set_ylim(0, 100)
    axC.set_ylabel("% of tasks", color="#dddddd")
    axC.set_title("C. Single-Option Bias Monitor\n(% tasks with >90% same-option preds)",
                  fontsize=11)
    axC.tick_params(axis="x", rotation=20)
    _style_ax(axC)

    # --- Panel D: per-task heatmap (models + references) --------------------------------
    axD = fig.add_subplot(gs[1, :])
    row_names = models + ["GPT-5.4-thinking", "Chance (Frequency)", "Human"]
    mat = np.full((len(row_names), len(TASKS)), np.nan)
    for i, m in enumerate(models):
        ta = per_task_acc(runs[m])
        for j, t in enumerate(TASKS):
            if t in ta:
                mat[i, j] = ta[t]
    for k, r in enumerate(["GPT-5.4-thinking", "Chance (Frequency)", "Human"]):
        mat[n_models + k, :] = REFERENCE[r][1]
    im = axD.imshow(np.ma.masked_invalid(mat), aspect="auto", cmap="RdYlGn",
                    vmin=30, vmax=100)
    axD.set_xticks(range(len(TASKS)))
    axD.set_xticklabels([t.replace(" ", "\n") for t in TASKS], fontsize=8)
    axD.set_yticks(range(len(row_names)))
    axD.set_yticklabels(row_names, fontsize=9)
    axD.tick_params(axis="y", pad=2)
    axD.yaxis.set_label_coords(-0.085, 0.5)
    for i in range(len(row_names)):
        for j in range(len(TASKS)):
            if not np.isnan(mat[i, j]):
                v = mat[i, j]
                axD.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7,
                         color="#f0f0f0" if (v < 45 or v > 90) else "#111111")
    # dimension separators
    for x in [2.5, 5.5, 11.5]:
        axD.axvline(x, color="#ffffff", lw=2)
    for x, d in zip([1, 4, 8.5, 13], DIMS):
        axD.text(x, -0.9, d, ha="center", fontsize=9, color="#ffd54f",
                 fontweight="bold")
    axD.set_title("D. Per-Task Accuracy Heatmap (NaN = task not run)", fontsize=12,
                  color="#f0f0f0")
    _style_ax(axD)
    cb = fig.colorbar(im, ax=axD, fraction=0.015, pad=0.01)
    cb.ax.tick_params(colors="#dddddd")

    fig.savefig(out_path, dpi=110, facecolor=MPL_BG)
    plt.close(fig)
    print(f"[overview] wrote {out_path}")


# ---------------------------------------------------------------------------
# Per-sample replay videos (cv2 -> ffmpeg libx264)
# ---------------------------------------------------------------------------
W, H = 1600, 900


def _draw_text_wrapped(img, text, x, y, max_w, scale=0.55, color=COLOR_TEXT,
                       thickness=1, line_h=22, max_lines=12):
    """Word-wrap text into panel; returns next y."""
    words = str(text).split()
    line, lines = "", []
    for w_ in words:
        trial = (line + " " + w_).strip()
        if cv2.getTextSize(trial, FONT, scale, thickness)[0][0] <= max_w:
            line = trial
        else:
            lines.append(line)
            line = w_
    lines.append(line)
    for ln in lines[:max_lines]:
        cv2.putText(img, ln, (x, y), FONT, scale, color, thickness, cv2.LINE_AA)
        y += line_h
    if len(lines) > max_lines:
        cv2.putText(img, f"... (+{len(lines) - max_lines} lines)", (x, y), FONT,
                    scale, COLOR_TEXT_DIM, thickness, cv2.LINE_AA)
        y += line_h
    return y


def _panel(img, x0, y0, x1, y1, title=None):
    cv2.rectangle(img, (x0, y0), (x1, y1), COLOR_PANEL, -1)
    cv2.rectangle(img, (x0, y0), (x1, y1), COLOR_PANEL_EDGE, 2)
    if title:
        cv2.putText(img, title, (x0 + 10, y0 + 24), FONT, 0.6, COLOR_ACCENT, 1,
                    cv2.LINE_AA)


def synthetic_frames(sample, n=16, w=640, h=400):
    """Deterministic synthetic clip when no real video exists (demo/smoke)."""
    seed = abs(hash(sample["id"])) % (2 ** 32)
    rng = np.random.default_rng(seed)
    bg = rng.integers(30, 90, size=(h, w, 3), dtype=np.uint8)
    vx, vy = rng.integers(4, 12, size=2)
    ok = bool(sample.get("correct", True))
    for t in range(n):
        fr = bg.copy()
        x = int(60 + vx * t * 3) % (w - 120)
        y = int(80 + vy * t * 2) % (h - 160)
        cv2.rectangle(fr, (x, y), (x + 90, y + 60), (0, 200, 0), 2)
        cv2.putText(fr, "TARGET", (x, y - 8), FONT, 0.5, (0, 200, 0), 1)
        cv2.circle(fr, (w - 80, h - 80), 25,
                   (0, 180, 255) if ok else (60, 80, 235), -1)
        cv2.putText(fr, f"[synthetic frame {t + 1}/{n}]", (10, h - 12), FONT, 0.45,
                    (200, 200, 200), 1)
        yield fr


def video_frames(sample, n=16, w=640, h=400):
    """Uniform n frames from the sample's video; falls back to synthetic frames."""
    path = sample.get("video") or ""
    if path and os.path.exists(path):
        cap = cv2.VideoCapture(path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total > 0:
            idxs = np.linspace(0, total - 1, n).astype(int)
            got = []
            for i in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
                ok, fr = cap.read()
                if ok:
                    got.append(cv2.resize(fr, (w, h)))
            cap.release()
            if got:
                while len(got) < n:  # pad tail if some reads failed
                    got.append(got[-1].copy())
                return got
        cap.release()
    return list(synthetic_frames(sample, n=n, w=w, h=h))


def render_sample_video(sample, out_path, n_frames=16, fps=2):
    frames = video_frames(sample, n=n_frames)
    correct = bool(sample.get("correct"))
    stamp = "MATCH" if correct else "MISMATCH"
    stamp_color = COLOR_MATCH if correct else COLOR_MISMATCH

    tmp_dir = tempfile.mkdtemp(prefix="vistr_vis_")
    for fi, vframe in enumerate(frames):
        canvas = np.full((H, W, 3), COLOR_BG, dtype=np.uint8)

        # Header
        cv2.putText(canvas, "ViSTR-Agent", (16, 34), FONT, 0.9, COLOR_TEXT, 2,
                    cv2.LINE_AA)
        cv2.putText(canvas, f"{sample['id']} | {sample['task']}", (230, 34), FONT,
                    0.7, COLOR_ACCENT, 1, cv2.LINE_AA)
        cv2.putText(canvas, f"Frame {fi + 1}/{len(frames)}", (W - 200, 34), FONT, 0.6,
                    COLOR_TEXT_DIM, 1, cv2.LINE_AA)
        cv2.line(canvas, (0, 48), (W, 48), COLOR_PANEL_EDGE, 2)

        # Video panel (left)
        _panel(canvas, 12, 60, 12 + 640 + 8, 60 + 400 + 34, "Video (uniform 16f)")
        canvas[60 + 30:60 + 30 + 400, 16:16 + 640] = vframe

        # Question + options (right top)
        _panel(canvas, 676, 60, W - 12, 300, "Question")
        y = _draw_text_wrapped(canvas, sample.get("question", ""), 688, 118,
                               W - 676 - 36, max_lines=5)
        opts = sample.get("options", [])
        for k, opt in enumerate(opts):
            col = COLOR_GT if opt == sample.get("gt") else COLOR_TEXT
            marker = " (GT)" if opt == sample.get("gt") else ""
            cv2.putText(canvas, f"[{chr(65 + k)}] {opt}{marker}", (688, y + 8), FONT,
                        0.6, col, 2 if opt == sample.get("gt") else 1, cv2.LINE_AA)
            y += 26

        # Evidence (right middle)
        _panel(canvas, 676, 312, W - 12, 556, "Tool Evidence (language-native summary)")
        _draw_text_wrapped(canvas, sample.get("evidence", "") or "(none)", 688, 370,
                           W - 676 - 36, max_lines=7, color=COLOR_TEXT_DIM)

        # Reasoning (bottom left)
        _panel(canvas, 12, 508, 12 + 640 + 8, H - 100, "Agent Reasoning")
        _draw_text_wrapped(canvas, sample.get("reasoning", ""), 24, 566, 620,
                           max_lines=10)

        # Verdict (bottom right)
        _panel(canvas, 676, 568, W - 12, H - 100)
        y = 622
        cv2.putText(canvas, f"GT:   {sample.get('gt', '?')}", (700, y), FONT, 0.8,
                    COLOR_GT, 2, cv2.LINE_AA)
        cv2.putText(canvas, f"Pred: {sample.get('pred', '?')}", (700, y + 44), FONT,
                    0.8, COLOR_TEXT, 2, cv2.LINE_AA)
        cv2.putText(canvas, stamp, (W - 330, y + 22), FONT, 1.1, stamp_color, 3,
                    cv2.LINE_AA)
        cv2.putText(canvas, f"model: {sample.get('model', '?')}", (700, y + 88), FONT,
                    0.5, COLOR_TEXT_DIM, 1, cv2.LINE_AA)
        dim = TASK_DIM.get(sample["task"], "?")
        cv2.putText(canvas, f"dimension: {dim}", (700, y + 116), FONT, 0.5,
                    COLOR_TEXT_DIM, 1, cv2.LINE_AA)

        cv2.imwrite(os.path.join(tmp_dir, f"{fi:06d}.png"), canvas)

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                    "-i", f"{tmp_dir}/%06d.png", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", out_path], check=True)
    for f_ in os.listdir(tmp_dir):
        os.remove(os.path.join(tmp_dir, f_))
    os.rmdir(tmp_dir)


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------
_DEMO_Q = {
    "Vehicle Movement": ("This is a driving video. Please determine whether the vehicle "
                         "in the green box shows subtle movement during the video. "
                         "Answer Yes or No.", ["Yes", "No"]),
    "Relative Velocity": ("This is a driving video. Please determine which vehicle is "
                          "moving faster: the vehicle in the green box or the vehicle in "
                          "the blue box. Answer Green or Blue.", ["Green", "Blue"]),
    "Ego Motion": ("This is a video recorded by a moving camera in an indoor scene. The "
                   "target object is the piano. Please determine the final position of "
                   "the target object relative to the camera. Answer Front-right or "
                   "Front-left.", ["Front-right", "Front-left"]),
    "Passage Feasibility": ("This is a video of a vehicle and traffic cones placed near "
                            "its driving path. Please predict whether the vehicle can "
                            "pass the cone-constrained area without touching any cone. "
                            "Answer Yes or No.", ["Yes", "No"]),
    "Basketball Shot": ("This is a video of a basketball shot. Please predict whether "
                        "the basketball will go into the hoop. Answer Yes or No.",
                        ["Yes", "No"]),
    "Jenga Stability": ("This is a video of a Jenga game. Please predict whether the "
                        "tower will remain stable after the block that the hand is "
                        "trying to pull out is removed. Answer Yes or No.", ["Yes", "No"]),
}


def make_demo_results(path, model="vistr-agent-demo", n_per_task=10, seed=31):
    rng = np.random.default_rng(seed)
    # per-task acc targets loosely shaped like a decent-but-flawed agent
    acc_target = {"Vehicle Movement": 0.7, "Relative Velocity": 0.6,
                  "Rotation Direction": 0.5, "Ego Motion": 0.8,
                  "Passage Feasibility": 0.7, "Interaction Direction": 0.6,
                  "Basketball Shot": 0.5, "Soccer Shot": 0.6, "Golf Shot": 0.5,
                  "Billiards Shot": 0.5, "Swimming Race": 0.5, "Fall Direction": 0.6,
                  "Jenga Stability": 0.6, "Mikado Dependency": 0.5, "Knot Type": 0.7}
    rows = []
    for t in TASKS:
        q, opts = _DEMO_Q.get(t, (f"This is a video of {t.lower()}. Please determine "
                                  f"the answer. Answer {t.split()[0]} or Other.",
                                  [t.split()[0], "Other"]))
        for i in range(n_per_task):
            gt = opts[int(rng.integers(0, 2))]
            hit = rng.random() < acc_target[t]
            pred = gt if hit else [o for o in opts if o != gt][0]
            rows.append({
                "id": f"{t.lower().replace(' ', '_')}_{i:04d}",
                "task": t, "dimension": TASK_DIM[t],
                "question": q, "options": opts, "gt": gt, "pred": pred,
                "correct": hit,
                "reasoning": ("<thinking> 1. Target Identification: located the target "
                              "via the visual prompt. 2. Motion Analysis: tracked the "
                              "target across the 16 sampled frames; displacement and "
                              "flow direction estimated. 3. Conclusion: extrapolated "
                              "the observed trend to the binary outcome. </thinking>"),
                "evidence": ("flow: dominant motion vector (vx=+3.2, vy=+0.4) px/frame; "
                             "track: target stable across 16/16 frames; "
                             "novel-view: N/A for this task"),
                "video": "", "model": model,
            })
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"[demo] wrote {len(rows)} samples -> {path}")
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="ViSTR-Bench results visualizer")
    ap.add_argument("--mode", choices=["overview", "samples", "all"], default="all")
    ap.add_argument("--results", nargs="*", default=None,
                    help="results JSONL files (default: all in outputs/predictions/)")
    ap.add_argument("--vis_dir", default=VIS_DIR)
    ap.add_argument("--max_samples", type=int, default=20,
                    help="max replay videos per run (samples mode)")
    ap.add_argument("--only_wrong", action="store_true",
                    help="samples mode: only render mismatched predictions")
    ap.add_argument("--demo", action="store_true",
                    help="generate demo results JSONL and visualize it")
    args = ap.parse_args()

    os.makedirs(args.vis_dir, exist_ok=True)

    if args.demo:
        demo_path = os.path.join(PRED_DIR, "demo_results.jsonl")
        make_demo_results(demo_path)
        args.results = [demo_path]

    if not args.results:
        args.results = sorted(
            os.path.join(PRED_DIR, f) for f in os.listdir(PRED_DIR)
            if f.endswith(".jsonl")) if os.path.isdir(PRED_DIR) else []
    if not args.results:
        raise SystemExit("No results JSONL found. Run with --demo for a smoke test.")

    runs = load_results(args.results)
    print(f"[load] {len(runs)} run(s): " +
          ", ".join(f"{m}={len(s)}" for m, s in runs.items()))

    if args.mode in ("overview", "all"):
        render_overview(runs, os.path.join(args.vis_dir, "overview_dashboard.png"))

    if args.mode in ("samples", "all"):
        out_dir = os.path.join(args.vis_dir, "samples")
        os.makedirs(out_dir, exist_ok=True)
        for model, samples in runs.items():
            todo = [s for s in samples if not s.get("correct")] if args.only_wrong \
                else samples
            todo = todo[:args.max_samples]
            for s in todo:
                out = os.path.join(out_dir, f"{s['id']}_replay.mp4")
                render_sample_video(s, out)
            print(f"[samples] {model}: wrote {len(todo)} replay video(s) -> {out_dir}")


if __name__ == "__main__":
    main()
