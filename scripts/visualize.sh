#!/bin/bash
# ViSTR-Bench results visualization wrapper.
# Usage:
#   bash scripts/visualize.sh                       # overview from all outputs/predictions/*.jsonl
#   bash scripts/visualize.sh --samples             # wrong-case replay videos (+ overview)
#   bash scripts/visualize.sh --demo                # smoke test with mock data
set -e
PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON=/opt/conda/bin/python

MODE_ARGS=(--mode overview)
for arg in "$@"; do
  case "$arg" in
    --samples) MODE_ARGS=(--mode all --only_wrong) ;;
    *) MODE_ARGS+=("$arg") ;;
  esac
done

exec "$PYTHON" -u "$PROJ_DIR/visualize_results.py" "${MODE_ARGS[@]}"
