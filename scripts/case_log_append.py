#!/usr/bin/env python
"""Append structured entries to the case review log (docs/notes/analyses/2026-08-01_case_review/case_log.jsonl)."""
import json
import os
import sys

REVIEW_DIR = "/mnt/xlab-nas-wm/gaozhe.gz/codes/PlayGround/0731-spatial_temperal_agent/docs/notes/analyses/2026-08-01_case_review"
LOG = os.path.join(REVIEW_DIR, "case_log.jsonl")


def append(entries):
    with open(LOG, "a") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"appended {len(entries)} -> {LOG} (total {sum(1 for _ in open(LOG))})")


if __name__ == "__main__":
    append(json.load(sys.stdin))
