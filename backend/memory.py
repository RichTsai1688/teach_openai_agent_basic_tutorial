from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from agents.memory import SQLiteSession

from .settings import MEMORY_DB_PATH


def init_memory_db(db_path: Path = MEMORY_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                message_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES agent_sessions (session_id)
                    ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_messages_session_id
            ON agent_messages (session_id, id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL DEFAULT 'user',
                key TEXT NOT NULL DEFAULT 'note',
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def new_session_id() -> str:
    return f"session-{uuid.uuid4().hex[:12]}"


def get_session(session_id: str) -> SQLiteSession:
    init_memory_db()
    return SQLiteSession(session_id=session_id, db_path=MEMORY_DB_PATH)


def list_sessions() -> list[dict[str, Any]]:
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT s.session_id, s.created_at, s.updated_at, COUNT(m.id) AS message_count
            FROM agent_sessions s
            LEFT JOIN agent_messages m ON m.session_id = s.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_session_messages(session_id: str) -> list[dict[str, Any]]:
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, message_data, created_at
            FROM agent_messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()

    messages = []
    for row in rows:
        try:
            message_data = json.loads(row["message_data"])
        except json.JSONDecodeError:
            message_data = row["message_data"]
        messages.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "message": message_data,
            }
        )
    return messages


def delete_session(session_id: str) -> None:
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute("DELETE FROM agent_messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM agent_sessions WHERE session_id = ?", (session_id,))
        conn.commit()


def list_memory() -> list[dict[str, Any]]:
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, scope, key, value, created_at, updated_at
            FROM user_memory
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def add_memory(scope: str, key: str, value: str) -> dict[str, Any]:
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            INSERT INTO user_memory (scope, key, value)
            VALUES (?, ?, ?)
            """,
            (scope.strip() or "user", key.strip() or "note", value.strip()),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id, scope, key, value, created_at, updated_at
            FROM user_memory
            WHERE id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def delete_memory(memory_id: int) -> None:
    init_memory_db()
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute("DELETE FROM user_memory WHERE id = ?", (memory_id,))
        conn.commit()


def memory_context() -> str:
    items = list_memory()
    if not items:
        return ""
    lines = [f"- {item['scope']}:{item['key']} = {item['value']}" for item in items[:12]]
    return "\n".join(lines)
