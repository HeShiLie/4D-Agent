"""
ViSTR-Bench Web Visualization Frontend — zero-dependency stdlib server.

Serves:
  /                     dashboard SPA (web/index.html)
  /api/config           tasks/dims/reference rows (paper Table II subset)
  /api/runs             available runs: benchmark GT pseudo-run + outputs/predictions/*.jsonl
  /api/overview         aggregate stats per run (overall / per-task / per-dim / bias)
  /api/samples          sample list, filterable by run/task/status
  /api/sample           full sample detail incl. video_url
  /video/<path>         video streaming with HTTP Range support (seekable)

Data schema is identical to visualize_results.py (see
docs/agent/skills/visualize_benchmark_results/SKILL.md).

Usage:
  /opt/conda/bin/python web_frontend.py [--port 8731] [--host 0.0.0.0]
"""
import argparse
import io
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
PRED_DIR = os.path.join(PROJ_DIR, "outputs", "predictions")
BENCH_DIR = os.path.join(PROJ_DIR, "data", "benchmarks", "ViSTR-Bench-Public")
WEB_DIR = os.path.join(PROJ_DIR, "web")

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
# Paper full-set reference (see docs/knowledge/vistr_bench.md)
REFERENCE = {
    "Human": {"avg": 91.0, "tasks": [90.6, 97.0, 100.0, 99.6, 85.5, 100.0, 81.5,
                                     82.9, 87.7, 77.3, 84.7, 100.0, 94.4, 98.8, 77.6]},
    "GPT-5.4-thinking": {"avg": 62.0, "tasks": [57.1, 75.0, 76.6, 75.6, 58.2, 87.5,
                                                46.8, 51.3, 54.7, 58.7, 50.0, 56.5,
                                                67.5, 47.0, 72.4]},
    "Chance (Frequency)": {"avg": 57.9, "tasks": [64.3, 59.5, 53.1, 53.4, 65.5, 83.9,
                                                  57.3, 52.5, 54.7, 53.3, 50.0, 58.7,
                                                  65.0, 54.2, 58.6]},
    "Chance (Random)": {"avg": 50.0, "tasks": [50.0] * 15},
}
BENCHMARK_RUN_ID = "__benchmark__"

# Video serving is restricted to these roots (symlinks resolved).
ALLOWED_ROOTS = [os.path.realpath(PROJ_DIR),
                 os.path.realpath(BENCH_DIR)]

_run_cache = {}


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------
def _norm_task(name):
    """'Basketball_Shot' -> 'Basketball Shot' (benchmark uses underscores)."""
    return str(name).replace("_", " ")


def _load_benchmark():
    """Benchmark GT as a pseudo-run (pred='', correct=None) for browsing."""
    path = os.path.join(BENCH_DIR, "data.json")
    if not os.path.exists(path):
        return None
    rows = json.load(open(path))
    samples = []
    for r in rows:
        samples.append({
            "id": f"bench_{r['id']}",
            "task": _norm_task(r["task"]),
            "dimension": _norm_task(r["dimension"]),
            "dataset": r.get("dataset", "?"),
            "question": r["direct_prompting"],
            "manual_cot": r.get("manual_cot_prompting", ""),
            "options": r["options"],
            "gt": r["answer"],
            "pred": "",
            "correct": None,
            "reasoning": "",
            "evidence": "",
            "video": r["video"],          # relative to BENCH_DIR
            "model": "benchmark (ground truth)",
        })
    return samples


def load_run(run_id):
    if run_id in _run_cache:
        return _run_cache[run_id]
    samples = None
    if run_id == BENCHMARK_RUN_ID:
        samples = _load_benchmark()
    else:
        path = os.path.join(PRED_DIR, run_id)
        if os.path.isfile(path) and run_id.endswith(".jsonl"):
            samples = [json.loads(l) for l in open(path) if l.strip()]
            for s in samples:
                s["task"] = _norm_task(s["task"])
    _run_cache[run_id] = samples
    return samples


def list_runs():
    runs = []
    if os.path.exists(os.path.join(BENCH_DIR, "data.json")):
        rows = _load_benchmark()
        runs.append({"id": BENCHMARK_RUN_ID, "model": "benchmark (ground truth)",
                     "n": len(rows), "is_benchmark": True})
    if os.path.isdir(PRED_DIR):
        for f in sorted(os.listdir(PRED_DIR)):
            if not f.endswith(".jsonl"):
                continue
            samples = load_run(f)
            if samples:
                runs.append({"id": f,
                             "model": samples[0].get("model") or f,
                             "n": len(samples), "is_benchmark": False})
    return runs


def overview_for(samples):
    def acc(ss):
        scored = [s for s in ss if s.get("correct") is not None]
        return round(100.0 * sum(1 for s in scored if s["correct"]) /
                     max(1, len(scored)), 1)
    per_task, per_dim = {}, {}
    for t in TASKS:
        ss = [s for s in samples if s["task"] == t]
        if ss:
            per_task[t] = {"acc": acc(ss), "n": len(ss)}
    for d in DIMS:
        ss = [s for s in samples if TASK_DIM.get(s["task"]) == d]
        if ss:
            per_dim[d] = {"acc": acc(ss), "n": len(ss)}
    # single-option bias: % tasks where one option >90% of predictions
    n_bias, n_tasks = 0, 0
    for t in {s["task"] for s in samples}:
        preds = [s["pred"] for s in samples if s["task"] == t and s.get("pred")]
        if not preds:
            continue
        n_tasks += 1
        if max(preds.count(v) for v in set(preds)) / len(preds) > 0.9:
            n_bias += 1
    return {"overall": acc(samples), "per_task": per_task, "per_dim": per_dim,
            "bias": {"frac": round(100.0 * n_bias / max(1, n_tasks), 1),
                     "n_bias": n_bias, "n_tasks": n_tasks},
            "n": len(samples)}


def taxonomy():
    """Aggregate benchmark metadata for the taxonomy page."""
    rows = _load_benchmark() or []
    dims = {}
    for d in DIMS:
        ds = [r for r in rows if r.get("dimension") == d]
        dims[d] = {"n": len(ds)}
    tasks = []
    for t in TASKS:
        ts = [r for r in rows if r["task"] == t]
        if not ts:
            continue
        ans = {}
        for r in ts:
            ans[r["gt"]] = ans.get(r["gt"], 0) + 1
        src = {}
        for r in ts:
            s = r.get("dataset") or "?"
            src[s] = src.get(s, 0) + 1
        qt = sorted({r["question"] for r in ts})
        tasks.append({"task": t, "dimension": TASK_DIM[t], "n": len(ts),
                      "answers": ans, "sources": src,
                      "n_templates": len(qt), "template": qt[0],
                      "poster": "/static/posters/" + t.replace(" ", "_") + ".jpg"})
    return {"total": len(rows), "dims": dims, "tasks": tasks}


def resolve_video(sample):
    """Map a sample's video field to a /video/ URL if the file exists."""
    v = sample.get("video") or ""
    if not v:
        return ""
    cands = [v] if os.path.isabs(v) else [os.path.join(BENCH_DIR, v),
                                          os.path.join(PROJ_DIR, v)]
    for c in cands:
        real = os.path.realpath(c)
        if os.path.isfile(real) and any(real.startswith(r + os.sep) or real == r
                                        for r in ALLOWED_ROOTS):
            return "/video/" + os.path.relpath(real, ALLOWED_ROOTS[0]) \
                if real.startswith(ALLOWED_ROOTS[0] + os.sep) \
                else "/video/@ext/" + os.path.relpath(real, ALLOWED_ROOTS[1])
    return ""


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "ViSTRWeb/1.1"
    protocol_version = "HTTP/1.1"  # keep-alive; required for browser range video

    def log_message(self, fmt, *args):  # quieter logs
        pass

    # -- helpers -----------------------------------------------------------
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _404(self, msg="not found"):
        self._json({"error": msg}, 404)

    # -- routing -----------------------------------------------------------
    def do_GET(self):
        u = urlparse(self.path)
        path = unquote(u.path)
        q = parse_qs(u.query)
        if path == "/" or path == "/index.html":
            return self._static("index.html", "text/html")
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if path == "/api/config":
            return self._json({"tasks": TASKS, "dims": DIMS, "task_dim": TASK_DIM,
                               "reference": REFERENCE})
        if path == "/api/runs":
            return self._json(list_runs())
        if path == "/api/taxonomy":
            return self._json(taxonomy())
        if path == "/api/overview":
            out = {}
            for rid in q.get("run", []):
                samples = load_run(rid)
                if samples:
                    out[rid] = overview_for(samples)
                    out[rid]["model"] = samples[0].get("model") or rid
            return self._json(out)
        if path == "/api/samples":
            return self._samples(q)
        if path == "/api/sample":
            return self._sample(q)
        if path.startswith("/video/"):
            return self._video(path[len("/video/"):])
        return self._404()

    # -- endpoints ---------------------------------------------------------
    def _samples(self, q):
        rid = q.get("run", [""])[0]
        samples = load_run(rid)
        if samples is None:
            return self._404("unknown run")
        task, status = q.get("task", [""])[0], q.get("status", ["all"])[0]
        text = q.get("q", [""])[0].lower()
        out = []
        for s in samples:
            if task and s["task"] != task:
                continue
            if status == "correct" and s.get("correct") is not True:
                continue
            if status == "wrong" and s.get("correct") is not False:
                continue
            if text and text not in (s["id"] + s.get("question", "")).lower():
                continue
            out.append({"id": s["id"], "task": s["task"], "correct": s.get("correct"),
                        "gt": s.get("gt"), "pred": s.get("pred")})
        self._json({"total": len(out), "samples": out[:2000]})

    def _sample(self, q):
        rid, sid = q.get("run", [""])[0], q.get("id", [""])[0]
        samples = load_run(rid)
        if samples is None:
            return self._404("unknown run")
        for s in samples:
            if s["id"] == sid:
                d = dict(s)
                d["video_url"] = resolve_video(s)
                return self._json(d)
        self._404("unknown sample id")

    def _static(self, rel, ctype=None):
        real = os.path.realpath(os.path.join(WEB_DIR, rel))
        if not real.startswith(os.path.realpath(WEB_DIR) + os.sep) or \
                not os.path.isfile(real):
            return self._404()
        ctype = ctype or {".js": "application/javascript; charset=utf-8",
                          ".css": "text/css; charset=utf-8",
                          ".html": "text/html; charset=utf-8",
                          ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                          ".png": "image/png",
                          }.get(os.path.splitext(real)[1],
                                "application/octet-stream")
        with open(real, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _video(self, rel):
        if rel.startswith("@ext/"):
            real = os.path.realpath(os.path.join(ALLOWED_ROOTS[1], rel[5:]))
        else:
            real = os.path.realpath(os.path.join(ALLOWED_ROOTS[0], rel))
        if not any(real.startswith(r + os.sep) for r in ALLOWED_ROOTS) or \
                not os.path.isfile(real):
            return self._404("video not found")
        size = os.path.getsize(real)
        range_h = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if range_h:
            m = re.match(r"bytes=(\d*)-(\d*)", range_h)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
                code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range",
                             f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(real, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1 << 20, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8731)
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[vistr-web] serving on http://{args.host}:{args.port}  "
          f"(predictions: {PRED_DIR})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
