from __future__ import annotations

import anyio
from fastmcp import Client

from fastmcp_stats_agent.server import mcp


async def main() -> None:
    async with Client(mcp) as client:
        health = await client.call_tool("database_health", {})
        assert health.data["ready"] is True
        assert health.data["case_count"] == 3

        describe = await client.call_tool("describe_case", {"case_id": "case_01"})
        assert describe.data["rows"] == 2160

        baseline = await client.call_tool(
            "baseline_profile_case",
            {
                "case_id": "case_01",
                "value_col": "vibration_mm_s",
                "baseline_rows": 8,
            },
        )
        assert baseline.data["baseline_rows"] == 8

        groups = await client.call_tool(
            "group_compare_case",
            {
                "case_id": "case_02",
                "group_col": "production_flag",
                "value_col": "flow_m3_min",
            },
        )
        assert len(groups.data["groups"]) >= 2

        autonomous = await client.call_tool("analyze_autonomous_sensing", {})
        assert autonomous.data["status"] == "abnormal"
        assert autonomous.data["evidence"]["event_count"] > 0

        leakage = await client.call_tool("analyze_night_leakage", {})
        assert leakage.data["status"] == "suspected_night_leakage"
        assert leakage.data["evidence"]["event_count"] > 0

        handover = await client.call_tool("build_shift_handover", {"case_id": "case_03"})
        assert handover.data["case_id"] == "case_06"
        assert handover.data["status"] == "handover_required"

    print("FastMCP SQLite stats agent direct test passed.")


if __name__ == "__main__":
    anyio.run(main)
