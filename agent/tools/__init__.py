"""ViSTR-Agent tools package.

Unified evidence schema (per plan 三阶段):
  {
    "tool":    str,                     # tool name
    "status":  "success"|"uncertain"|"failed",
    "summary": str,                     # language-native evidence (for VLM/verifier)
    "data":    dict,                    # structured, schema-parseable fields
    "viz":     str|None,                # visualization artifact path
  }
Tools NEVER output the final Yes/No answer — they output evidence.
Decision rules live in the task pipelines (agent/pipelines/).
"""
import os

PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
BENCH_DIR = os.path.join(PROJ_DIR, "data", "benchmarks", "ViSTR-Bench-Public")
VIZ_DIR = os.path.join(PROJ_DIR, "outputs", "tool_viz")
os.makedirs(VIZ_DIR, exist_ok=True)


def evidence(tool, status, summary, data, viz=None):
    return {"tool": tool, "status": status, "summary": summary,
            "data": data, "viz": viz}
