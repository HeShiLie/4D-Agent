"""Batch evaluation for Coding Agent pipeline.

Usage:
    python agent/coding_agent/eval_coding_agent.py [--split dev|eval|all] [--tasks T1,T2,...] [--limit N] [--resume]

Writes JSONL to outputs/predictions/coding_agent_<timestamp>.jsonl with checkpoint/resume.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from agent.coding_agent.pipeline import solve_sample


DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "benchmarks", "ViSTR-Bench-Public", "data.json")
SPLIT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "configs", "split.json")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "outputs", "predictions")


def load_samples(split: str = "dev", tasks: list[str] | None = None,
                 limit: int | None = None) -> list[dict]:
    with open(DATA_PATH) as f:
        data = json.load(f)
    with open(SPLIT_PATH) as f:
        split_cfg = json.load(f)

    data_by_id = {s["id"]: s for s in data}

    if split == "all":
        samples = data
    else:
        ids = []
        for task_ids in split_cfg.values():
            ids.extend(task_ids.get(split, []))
        samples = [data_by_id[i] for i in ids if i in data_by_id]

    if tasks:
        samples = [s for s in samples if s["task"] in tasks]

    if limit:
        samples = samples[:limit]

    return samples


def run_eval(samples: list[dict], output_path: str, workers: int = 1,
             timeout: int = 90, resume: bool = False):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    done_ids = set()
    if resume and os.path.exists(output_path):
        with open(output_path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done_ids.add(r["id"])
                except (json.JSONDecodeError, KeyError):
                    pass
        print(f"Resuming: {len(done_ids)} already done")

    remaining = [s for s in samples if s["id"] not in done_ids]
    print(f"Running {len(remaining)} samples (workers={workers}, timeout={timeout}s)")

    t0 = time.time()
    results = []

    def _run(sample):
        return solve_sample(sample, timeout=timeout)

    with open(output_path, "a") as fout:
        if workers <= 1:
            for i, sample in enumerate(remaining):
                result = _run(sample)
                results.append(result)
                fout.write(json.dumps(result, ensure_ascii=False) + "\n")
                fout.flush()
                ok = "✓" if result["correct"] else "✗"
                print(f"[{i+1}/{len(remaining)}] {ok} {result['task']}[{result['id']}] "
                      f"src={result['src']} pred={result['pred']} "
                      f"elapsed={result.get('elapsed_s', 0):.1f}s")
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_run, s): s for s in remaining}
                for i, future in enumerate(as_completed(futures)):
                    result = future.result()
                    results.append(result)
                    fout.write(json.dumps(result, ensure_ascii=False) + "\n")
                    fout.flush()
                    ok = "✓" if result["correct"] else "✗"
                    print(f"[{i+1}/{len(remaining)}] {ok} {result['task']}[{result['id']}] "
                          f"src={result['src']} pred={result['pred']}")

    elapsed = time.time() - t0
    correct = sum(1 for r in results if r["correct"])
    total = len(results)

    print(f"\n{'='*50}")
    print(f"Results: {correct}/{total} = {correct/total*100:.1f}%")
    print(f"Time: {elapsed:.0f}s ({elapsed/max(total,1):.1f}s/sample)")
    print(f"Output: {output_path}")

    # Per-task breakdown
    by_task = {}
    for r in results:
        by_task.setdefault(r["task"], [0, 0])
        by_task[r["task"]][1] += 1
        if r["correct"]:
            by_task[r["task"]][0] += 1
    print(f"\nPer-task:")
    for task in sorted(by_task):
        c, t = by_task[task]
        print(f"  {task}: {c}/{t} = {c/t*100:.0f}%")

    # Per-source breakdown
    by_src = {}
    for r in results:
        by_src.setdefault(r["src"], [0, 0])
        by_src[r["src"]][1] += 1
        if r["correct"]:
            by_src[r["src"]][0] += 1
    print(f"\nPer-source:")
    for src in sorted(by_src):
        c, t = by_src[src]
        print(f"  {src}: {c}/{t} = {c/t*100:.0f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["dev", "eval", "all"])
    parser.add_argument("--tasks", type=str, default="", help="Comma-separated task names")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()

    tasks_filter = [t.strip() for t in args.tasks.split(",") if t.strip()] or None
    samples = load_samples(args.split, tasks_filter, args.limit)
    print(f"Loaded {len(samples)} samples (split={args.split}, tasks={tasks_filter})")

    if not args.output:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = os.path.join(OUTPUT_DIR, f"coding_agent_{ts}.jsonl")

    run_eval(samples, args.output, workers=args.workers,
             timeout=args.timeout, resume=args.resume)
