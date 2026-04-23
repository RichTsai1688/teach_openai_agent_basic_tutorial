from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    case_id: str | None = None
    use_memory: bool = True


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggested_next_actions: list[str] = Field(default_factory=list)


class MemoryCreateRequest(BaseModel):
    scope: str = "user"
    key: str = "note"
    value: str


class MemoryItem(BaseModel):
    id: int
    scope: str
    key: str
    value: str
    created_at: str
    updated_at: str
