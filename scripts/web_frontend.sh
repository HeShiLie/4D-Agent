#!/bin/bash
# ViSTR-Bench web visualization frontend (Streamlit).
# Usage:
#   bash scripts/web_frontend.sh [--port 8731]        # foreground
#   nohup bash scripts/web_frontend.sh > /tmp/vistr_streamlit.log 2>&1 &   # background
set -e
PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY=/opt/conda/envs/python3.10.13/bin/python   # 与 48901 同款 streamlit 环境
PORT="${1:-8731}"
exec "$PY" -m streamlit run "$PROJ_DIR/scripts/vistr_viewer.py" \
  --server.port "$PORT" --server.headless true
