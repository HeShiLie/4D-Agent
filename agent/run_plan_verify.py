#!/usr/bin/env python
"""Phase-2 runner: plan + verify (isolated contexts) over ViSTR-Bench public split.

Usage:
  /opt/conda/bin/python -u agent/run_plan_verify.py --limit 5        # smoke
  nohup /opt/conda/bin/python -u agent/run_plan_verify.py > /tmp/pv.log 2>&1 &   # full 670

Output: outputs/plan_verify/qwen3-vl-plus_plan_verify.jsonl (checkpoint/resume by id)
"""
import argparse
import base64
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent import llm, prompts

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_DIR = os.path.join(PROJ_DIR, "data", "benchmarks", "ViSTR-Bench-Public")
OUT_DIR = os.path.join(PROJ_DIR, "outputs", "plan_verify")
OUT_PATH = os.path.join(OUT_DIR, "qwen3-vl-plus_plan_verify.jsonl")

N_FRAMES = 16
FRAME_W, FRAME_H = 640, 360


def extract_frames(video_path, n=N_FRAMES):
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        cap.release()
        return []
    out = []
    for i in [round(j * (total - 1) / (n - 1)) for j in range(n)]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = cap.read()
        if not ok:
            continue
        fr = cv2.resize(fr, (FRAME_W, FRAME_H))
        out.append(base64.b64encode(
            cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 70])[1]).decode())
    cap.release()
    return out


def parse_tag(text, tag):
    m = re.search(rf"<{tag}>(.*?)(?:</{tag}>|$)", text, re.S)
    return m.group(1).strip() if m else ""


def parse_answer(text, options):
    ans = parse_tag(text, "answer").strip().strip("。.")
    for o in options:
        if ans == o or o.lower() in ans.lower():
            return o
    return ans or None


def parse_conf(text):
    m = re.search(r"(\d{1,3})", parse_tag(text, "confidence"))
    return min(100, int(m.group(1))) if m else None


def process(row):
    frames = extract_frames(os.path.join(BENCH_DIR, row["video"]))
    if len(frames) < 4:
        return {"id": row["id"], "error": f"only {len(frames)} frames"}
    q, opts = row["direct_prompting"], row["options"]
    t0 = time.time()
    # PLAN context (isolated call #1)
    plan_raw = llm.chat(prompts.build_messages(
        prompts.PLAN_PROMPT, q, opts, frames), max_tokens=2000)["content"]
    plan_text = parse_tag(plan_raw, "plan")
    # VERIFY context (isolated call #2 — sees plan's evidence list but NOT its answer)
    verify_raw = llm.chat(prompts.build_messages(
        prompts.VERIFY_PROMPT, q, opts, frames, plan_text=plan_text),
        max_tokens=3500)["content"]
    plan_ans = parse_answer(plan_raw, opts)
    verify_ans = parse_answer(verify_raw, opts)
    return {
        "id": row["id"], "task": row["task"].replace("_", " "),
        "dimension": row["dimension"].replace("_", " "),
        "dataset": row.get("dataset", "?"),
        "question": q, "options": opts, "gt": row["answer"],
        "video": row["video"], "model": llm.MODEL,
        "prompt_version": "v2",
        "plan": {
            "raw": plan_raw,
            "plan_text": plan_text,
            "answer": plan_ans,
            "confidence": parse_conf(plan_raw),
            "correct": plan_ans == row["answer"],
        },
        "verify": {
            "raw": verify_raw,
            "criteria": parse_tag(verify_raw, "acceptance_criteria"),
            "self_check": parse_tag(verify_raw, "self_check"),
            "answer": verify_ans,
            "confidence": parse_conf(verify_raw),
            "correct": verify_ans == row["answer"],
        },
        "agree": plan_ans is not None and plan_ans == verify_ans,
        "elapsed_s": round(time.time() - t0, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0 = all 670")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--task", default="", help="only this task (underscored)")
    args = ap.parse_args()

    rows = json.load(open(os.path.join(BENCH_DIR, "data.json")))
    if args.task:
        rows = [r for r in rows if r["task"] == args.task]
    done = set()
    if os.path.exists(OUT_PATH):
        for l in open(OUT_PATH):
            try:
                done.add(json.loads(l)["id"])
            except Exception:
                pass
    todo = [r for r in rows if r["id"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[plan_verify] total={len(rows)} done={len(done)} todo={len(todo)} "
          f"workers={args.workers} -> {OUT_PATH}", flush=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    t0 = time.time()
    n_ok = 0
    with open(OUT_PATH, "a") as fout, ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(process, r): r for r in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"id": r["id"], "error": str(e)[:300]}
            fout.write(json.dumps(res, ensure_ascii=False) + "\n")
            fout.flush()
            if "error" not in res:
                n_ok += 1
            if i % 10 == 0 or i == len(todo):
                el = time.time() - t0
                print(f"[{i}/{len(todo)}] ok={n_ok} elapsed={el/60:.1f}min "
                      f"eta={(el/max(i,1))*(len(todo)-i)/60:.1f}min", flush=True)
    print(f"[done] {n_ok}/{len(todo)} ok in {(time.time()-t0)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
