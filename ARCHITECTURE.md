# FastMCP SQLite Agent Architecture

## 整體架構

```mermaid
flowchart LR
  User["使用者"] --> FE["Frontend Chat UI<br/>frontend/index.html + app.js"]

  FE -->|HTTP API| BE["FastAPI Backend<br/>backend/app.py"]

  BE --> Memory["Memory DB<br/>data/agent_memory.sqlite"]
  BE --> AgentSvc["Agent Service<br/>backend/agent_service.py"]

  AgentSvc --> Runtime["Agent Runtime<br/>agent_runtime.py"]
  Runtime --> Agent["OpenAI Agents SDK<br/>設備工程師 Agent"]

  Agent -->|RAG tools| RAG["Local RAG Tools<br/>rag_agent_tools.py"]
  Agent -->|MCP stdio| MCP["FastMCP Server<br/>fastmcp_stats_agent/server.py"]

  MCP --> SQLite["Teaching SQLite DB<br/>air_compressor_teaching_cases.sqlite"]

  SQLite --> Case01["Case 01<br/>自主感測"]
  SQLite --> Case02["Case 02<br/>智慧監控"]
  SQLite --> Case06["Case 06<br/>自動交班資料"]

  FE --> Evidence["工具證據 / 下一步建議 UI"]
```

## 一次聊天請求順序

```mermaid
sequenceDiagram
  participant U as 使用者
  participant FE as Frontend
  participant API as FastAPI Backend
  participant MEM as SQLiteSession / User Memory
  participant RT as agent_runtime.py
  participant AG as OpenAI Agent
  participant MCP as FastMCP stdio server
  participant DB as air_compressor_teaching_cases.sqlite

  U->>FE: 輸入問題並選擇 case_id
  FE->>API: POST /api/chat
  API->>MEM: 讀取 session memory / user memory
  API->>RT: run_equipment_agent_result(message, session)
  RT->>MCP: 啟動 MCPServerStdio 並 connect
  RT->>AG: Runner.run(agent, message)

  AG->>MCP: 呼叫 scenario tool
  Note over AG,MCP: Case 01 -> analyze_autonomous_sensing<br/>Case 02 -> analyze_night_leakage<br/>Case 03 -> build_shift_handover(case_06)

  MCP->>DB: 查 cases / observations / events
  DB-->>MCP: 回傳資料
  MCP-->>AG: 回傳 summary + evidence + next actions

  AG-->>RT: 產生繁體中文回答
  RT->>MCP: cleanup
  RT-->>API: RunResult
  API->>MEM: 寫入對話 session
  API-->>FE: answer + tool_calls + evidence + suggested_next_actions
  FE-->>U: 顯示回答、工具證據、下一步建議
```

## Backend API 路由

```mermaid
flowchart TD
  API["FastAPI backend/app.py"] --> Health["GET /api/health<br/>檢查 Backend / SQLite / MCP"]
  API --> Cases["GET /api/cases<br/>列出案例"]
  API --> CaseDetail["GET /api/cases/{case_id}<br/>案例 metadata"]
  API --> Chat["POST /api/chat<br/>執行 Agent + MCP"]
  API --> Sessions["GET /api/sessions<br/>列 session"]
  API --> Messages["GET /api/sessions/{id}/messages<br/>查對話"]
  API --> DeleteSession["DELETE /api/sessions/{id}<br/>清除 session"]
  API --> MemoryList["GET /api/memory<br/>列 user memory"]
  API --> MemoryAdd["POST /api/memory<br/>新增 memory"]
  API --> MemoryDelete["DELETE /api/memory/{id}<br/>刪除 memory"]
```

## 主要檔案

- `frontend/index.html`：聊天介面 HTML。
- `frontend/app.js`：呼叫 backend API、渲染訊息、工具證據與 memory。
- `frontend/style.css`：聊天介面樣式。
- `backend/app.py`：FastAPI app 與 API routes。
- `backend/agent_service.py`：封裝 chat request、memory context、agent run 與 evidence 回傳。
- `backend/memory.py`：session memory 與 user memory SQLite helper。
- `backend/schemas.py`：API request / response schemas。
- `backend/settings.py`：專案路徑、SQLite DB path、frontend root。
- `agent_runtime.py`：建立 OpenAI Agents SDK agent 與 `MCPServerStdio` bridge。
- `main.py`：CLI 單次執行 agent 的入口。
- `curated_fastmcp_sqlite_teaching_case/fastmcp_stats_agent/server.py`：FastMCP tools 與 SQLite scenario analysis。
- `curated_fastmcp_sqlite_teaching_case/data/air_compressor_teaching_cases.sqlite`：教學案例資料庫。

## Case 對應

| UI/任務 | Backend case_id | SQLite 實際資料 | MCP scenario tool |
| --- | --- | --- | --- |
| Case 01 自主感測 | `case_01` | `case01_sensor_observations` | `analyze_autonomous_sensing` |
| Case 02 智慧監控 | `case_02` | `case02_monitoring_observations` | `analyze_night_leakage` |
| 案例 3 自動交班 | `case_03` alias | `case_06` / `case06_logbook_observations` | `build_shift_handover` |

## 啟動方式

```bash
./.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

開啟：

```text
http://127.0.0.1:8000
```

