#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR"

./.venv/bin/pip install -r requirements.txt
./.venv/bin/python fastmcp_stats_agent/generate_mcp_configs.py
./.venv/bin/python -m py_compile fastmcp_stats_agent/server.py
./.venv/bin/python fastmcp_stats_agent/test_client.py
./.venv/bin/python fastmcp_stats_agent/test_stdio_config.py
