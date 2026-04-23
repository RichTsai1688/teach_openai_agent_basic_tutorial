from __future__ import annotations

import anyio
from fastmcp import Client

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = CASE_ROOT / "data" / "air_compressor_teaching_cases.sqlite"

CONFIG = {
    "mcpServers": {
        "air-compressor-stats": {
            "command": str(REPO_ROOT / ".venv" / "bin" / "python"),
            "args": [str(CASE_ROOT / "fastmcp_stats_agent" / "server.py")],
            "cwd": str(CASE_ROOT),
            "env": {
                "PYTHONPATH": str(CASE_ROOT),
                "AIR_COMPRESSOR_DB_PATH": str(DB_PATH),
            },
            "transport": "stdio",
            "description": "Air compressor statistics tools for AI-agent classroom demos",
        }
    }
}


async def main() -> None:
    async with Client(CONFIG) as client:
        health = await client.call_tool("database_health", {})
        assert health.data["ready"] is True
        assert health.data["case_count"] == 3

        describe = await client.call_tool("describe_case", {"case_id": "case_01"})
        assert describe.data["rows"] == 2160

        autonomous = await client.call_tool("analyze_autonomous_sensing", {})
        assert autonomous.data["status"] == "abnormal"

        leakage = await client.call_tool("analyze_night_leakage", {})
        assert leakage.data["status"] == "suspected_night_leakage"

        handover = await client.call_tool("build_shift_handover", {"case_id": "case_03"})
        assert handover.data["case_id"] == "case_06"
        assert handover.data["status"] == "handover_required"

    print("FastMCP SQLite stdio config test passed.")


if __name__ == "__main__":
    anyio.run(main)
