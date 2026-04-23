from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .agent_service import case_payload, cases_payload, mcp_health, run_chat, sqlite_health_payload
from .memory import (
    add_memory,
    delete_memory,
    delete_session,
    get_session_messages,
    init_memory_db,
    list_memory,
    list_sessions,
)
from .schemas import ChatRequest, ChatResponse, MemoryCreateRequest
from .settings import FRONTEND_ROOT

app = FastAPI(title="Air Compressor Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    init_memory_db()


@app.get("/api/health")
async def health() -> dict:
    sqlite_status = sqlite_health_payload()
    try:
        mcp_status = await mcp_health()
    except Exception as exc:
        mcp_status = {"ready": False, "error": str(exc)}
    return {
        "backend": {"ready": True},
        "sqlite": sqlite_status,
        "mcp": mcp_status,
    }


@app.get("/api/cases")
async def cases() -> dict:
    return cases_payload()


@app.get("/api/cases/{case_id}")
async def case_detail(case_id: str) -> dict:
    try:
        return case_payload(case_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await run_chat(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/sessions")
async def sessions() -> dict:
    return {"sessions": list_sessions()}


@app.get("/api/sessions/{session_id}/messages")
async def session_messages(session_id: str) -> dict:
    return {"session_id": session_id, "messages": get_session_messages(session_id)}


@app.delete("/api/sessions/{session_id}")
async def remove_session(session_id: str) -> dict:
    delete_session(session_id)
    return {"ok": True}


@app.get("/api/memory")
async def memory() -> dict:
    return {"memory": list_memory()}


@app.post("/api/memory")
async def create_memory(request: MemoryCreateRequest) -> dict:
    if not request.value.strip():
        raise HTTPException(status_code=400, detail="Memory value cannot be empty.")
    return {"memory": add_memory(request.scope, request.key, request.value)}


@app.delete("/api/memory/{memory_id}")
async def remove_memory(memory_id: int) -> dict:
    delete_memory(memory_id)
    return {"ok": True}


if FRONTEND_ROOT.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
