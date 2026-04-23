from __future__ import annotations

from typing import Any

from agent_runtime import create_air_compressor_mcp_server, run_equipment_agent_result

from .memory import get_session, memory_context, new_session_id
from .schemas import ChatRequest, ChatResponse
from .settings import TEACHING_DB_PATH

from fastmcp_stats_agent.server import (
    analyze_autonomous_sensing,
    analyze_night_leakage,
    build_shift_handover,
    database_health,
    get_case_overview,
    list_cases,
)


def _selected_case_context(case_id: str | None) -> str:
    if not case_id:
        return ""
    return f"使用者目前選擇的案例是 {case_id}。請優先使用對應的 MCP scenario tool。"


def _build_agent_input(request: ChatRequest, memory_text: str) -> str:
    parts = []
    selected = _selected_case_context(request.case_id)
    if selected:
        parts.append(selected)
    if request.use_memory and memory_text:
        parts.append(f"可用使用者記憶：\n{memory_text}")
    parts.append(f"本次使用者問題：\n{request.message}")
    return "\n\n".join(parts)


def _scenario_evidence(case_id: str | None) -> dict[str, Any]:
    if not case_id:
        return {}
    normalized = case_id.strip().lower()
    if normalized in {"case_01", "case_1"}:
        return analyze_autonomous_sensing(db_path=str(TEACHING_DB_PATH))
    if normalized in {"case_02", "case_2"}:
        return analyze_night_leakage(db_path=str(TEACHING_DB_PATH))
    if normalized in {"case_03", "case_3", "case_06", "case_6"}:
        return build_shift_handover(case_id=normalized, db_path=str(TEACHING_DB_PATH))
    return {}


def summarize_run_tool_calls(result: Any) -> list[dict[str, Any]]:
    tool_calls = []
    for item in getattr(result, "new_items", []) or []:
        raw = getattr(item, "raw_item", None)
        item_type = raw.get("type") if isinstance(raw, dict) else getattr(raw, "type", None)
        if item_type is None:
            item_type = type(item).__name__
        name = raw.get("name") if isinstance(raw, dict) else getattr(raw, "name", None)
        if name or "Tool" in str(item_type) or "MCP" in str(item_type):
            tool_calls.append({"type": str(item_type), "name": name or ""})
    return tool_calls


async def mcp_health() -> dict[str, Any]:
    server = create_air_compressor_mcp_server()
    await server.connect()
    try:
        tools = await server.list_tools()
        names = sorted(tool.name for tool in tools)
        return {
            "ready": True,
            "tool_count": len(names),
            "tools": names,
        }
    finally:
        await server.cleanup()


async def run_chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or new_session_id()
    session = get_session(session_id)
    memory_text = memory_context() if request.use_memory else ""
    agent_input = _build_agent_input(request, memory_text)
    result = await run_equipment_agent_result(agent_input, session=session)
    evidence = _scenario_evidence(request.case_id)
    return ChatResponse(
        session_id=session_id,
        answer=str(result.final_output),
        tool_calls=summarize_run_tool_calls(result),
        evidence=evidence.get("evidence", evidence),
        suggested_next_actions=evidence.get("suggested_next_actions", []),
    )


def cases_payload() -> dict[str, Any]:
    return list_cases(db_path=str(TEACHING_DB_PATH))


def case_payload(case_id: str) -> dict[str, Any]:
    return get_case_overview(case_id, db_path=str(TEACHING_DB_PATH))


def sqlite_health_payload() -> dict[str, Any]:
    return database_health(db_path=str(TEACHING_DB_PATH))
