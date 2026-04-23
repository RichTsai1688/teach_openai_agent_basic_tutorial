from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents import Agent, Runner, ToolSearchTool, WebSearchTool, function_tool, tool_namespace
from agents.mcp import MCPServer, MCPServerStdio
from agents.memory import Session

from rag_agent_tools import rag_index_status, rag_retrieve, rag_search

PROJECT_ROOT = Path(__file__).resolve().parent
CASE_ROOT = PROJECT_ROOT / "curated_fastmcp_sqlite_teaching_case"
MCP_SERVER_PATH = CASE_ROOT / "fastmcp_stats_agent" / "server.py"
AIR_COMPRESSOR_DB_PATH = CASE_ROOT / "data" / "air_compressor_teaching_cases.sqlite"
PYTHON_BIN = PROJECT_ROOT / ".venv" / "bin" / "python"


@function_tool(defer_loading=True)
def get_current_time() -> str:
    """Return the current local timestamp."""
    return datetime.now().isoformat()


crm_tools = tool_namespace(
    name="custom",
    description="custom tools for simple local utility lookups.",
    tools=[get_current_time],
)

local_rag_tools = tool_namespace(
    name="rag",
    description="local FAISS RAG tools for searching the prepared composite_v2 knowledge index.",
    tools=[rag_search, rag_retrieve, rag_index_status],
)

AGENT_INSTRUCTIONS = """
你是設備工程師 AI-agent。回答必須簡單、專業、繁體中文。

一般教材、課程、文件或 composite_v2 知識庫問題，先使用 rag tools。
需要直接根據資料回答時用 rag_search；需要先檢視來源片段再整合時用 rag_retrieve。

遇到空壓機教學案例、異常診斷、夜間漏氣、交班摘要時，必須先使用 air-compressor-stats MCP tools，不可直接憑直覺下結論。
Case 01 自主感測使用 analyze_autonomous_sensing。
Case 02 智慧監控或夜間漏氣使用 analyze_night_leakage。
自動交班、案例 3、Case 03 目前使用 build_shift_handover；此資料庫中實際資料表對應 case_06。

空壓機案例回答要包含：
1. 異常狀態
2. 主要證據
3. 最值得注意的時間、區域或訊號
4. 下一步建議

如果 MCP server 或 SQLite health check 失敗，請明確告知無法完成資料查證，不要自行猜測。
""".strip()


def create_air_compressor_mcp_server() -> MCPServerStdio:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(CASE_ROOT),
            "AIR_COMPRESSOR_DB_PATH": str(AIR_COMPRESSOR_DB_PATH),
        }
    )
    return MCPServerStdio(
        name="air-compressor-stats",
        params={
            "command": str(PYTHON_BIN),
            "args": [str(MCP_SERVER_PATH)],
            "cwd": str(CASE_ROOT),
            "env": env,
        },
        cache_tools_list=True,
        client_session_timeout_seconds=20,
    )


def create_equipment_agent(mcp_servers: list[MCPServer] | None = None) -> Agent:
    return Agent(
        name="設備工程師",
        instructions=AGENT_INSTRUCTIONS,
        model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
        tools=[WebSearchTool(), ToolSearchTool(), *crm_tools, *local_rag_tools],
        mcp_servers=mcp_servers or [],
    )


async def run_equipment_agent(
    message: str,
    *,
    session: Session | None = None,
    max_turns: int = 10,
) -> str:
    result = await run_equipment_agent_result(message, session=session, max_turns=max_turns)
    return str(result.final_output)


async def run_equipment_agent_result(
    message: str,
    *,
    session: Session | None = None,
    max_turns: int = 10,
):
    mcp_server = create_air_compressor_mcp_server()
    await mcp_server.connect()
    try:
        agent = create_equipment_agent([mcp_server])
        result = await Runner.run(agent, message, session=session, max_turns=max_turns)
        return result
    finally:
        await mcp_server.cleanup()
