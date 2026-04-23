from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = PROJECT_ROOT / "curated_fastmcp_sqlite_teaching_case"
TEACHING_DB_PATH = CASE_ROOT / "data" / "air_compressor_teaching_cases.sqlite"
MEMORY_DB_PATH = PROJECT_ROOT / "data" / "agent_memory.sqlite"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"

if str(CASE_ROOT) not in sys.path:
    sys.path.append(str(CASE_ROOT))

os.environ.setdefault("AIR_COMPRESSOR_DB_PATH", str(TEACHING_DB_PATH))
