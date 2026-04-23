# FastMCP SQLite Agent Development Checklist

## Goal

將 `curated_fastmcp_sqlite_teaching_case/fastmcp_stats_agent` 以 stdio MCP server 啟動，讓 `main.py` 的 OpenAI Agents SDK agent 可以呼叫空壓機教學案例的統計工具，並透過聊天介面回覆使用者：

- Case 01 自主感測：用 MCP 統計流程判斷多個感測訊號是否異常。
- Case 02 智慧監控：比較生產與非生產時段，判斷夜間漏氣或浪費。
- 自動交班摘要：整理重複異常成交班摘要。注意目前 SQLite 裡對應的資料是 `case_06`，可在 UI 顯示為「任務 3 自動交班」，但 backend 預設應對應 `case_06`，除非要重建 DB 改成 `case_03`。

## Implementation Status

- [x] 已建立分支 `codex/fastmcp-sqlite-agent`。
- [x] `fastmcp_stats_agent/server.py` 已可連 `data/air_compressor_teaching_cases.sqlite`。
- [x] 已新增 SQLite tools：`database_health`、`list_cases`、`describe_case`、`baseline_profile_case`、`rolling_anomaly_scan_case`、`group_compare_case`、`correlation_report_case`。
- [x] 已新增 scenario tools：`analyze_autonomous_sensing`、`analyze_night_leakage`、`build_shift_handover`。
- [x] 已修正 stdio config 產生器與 stdio 測試。
- [x] `main.py` 已透過 `agent_runtime.py` 使用 `MCPServerStdio` 橋接 MCP。
- [x] 已建立 FastAPI backend、session memory、user memory API。
- [x] 已建立無 build step 的 frontend chat UI。
- [x] 已完成 direct MCP、stdio MCP、backend health、backend chat integration smoke test。

## Current Validation

- [x] 已確認 SQLite 檔案存在：
  - `curated_fastmcp_sqlite_teaching_case/data/air_compressor_teaching_cases.sqlite`
- [x] 已確認 SQLite 可連線並讀取 `cases`：
  - `case_01` -> `case01_sensor_observations`, 2160 rows
  - `case_02` -> `case02_monitoring_observations`, 360 rows
  - `case_06` -> `case06_logbook_observations`, 480 rows
- [x] 已確認 `v_case_overview`、`case_events`、`fastmcp_recommended_checks` 可查詢。
- [x] 已確認 `fastmcp_recommended_checks` 已有三個案例的工具建議流程。
- [ ] 尚未確認 `fastmcp_stats_agent` 可直接連 SQLite，因為目前 `server.py` 只提供 CSV 讀取工具，尚未讀取 `data/air_compressor_teaching_cases.sqlite`。
- [ ] 尚未通過現有 stdio 測試，原因是目前 repo `.venv` 缺少 `fastmcp` 套件。
- [ ] 既有 `mcp_configs/generated/*.json` 指向舊專案路徑，需重新產生。
- [ ] `test_stdio_config.py` 的 stdio 設定需修正成本 repo 的實際路徑與 `.venv` 位置。

## Phase 1 - Environment And Blocking Checks

- [ ] 安裝或確認 runtime dependencies：
  - `fastmcp>=2.12`
  - `pandas>=2.0`
  - `fastapi`
  - `uvicorn`
  - `python-dotenv`
- [ ] 新增或更新專案根目錄 requirements，例如 `requirements.txt` 或 `requirements-dev.txt`。
- [ ] 執行 SQLite smoke test：
  - 查 `select * from v_case_overview order by case_id;`
  - 查 `select case_id, step_order, tool_name from fastmcp_recommended_checks order by case_id, step_order;`
- [ ] 修正 `fastmcp_stats_agent/generate_mcp_configs.py` 或重新產生 MCP config，確保 cwd、command、args、PYTHONPATH 都指向目前 repo。
- [ ] 修正 `fastmcp_stats_agent/test_stdio_config.py`，讓它從本 repo 啟動 server。
- [ ] 新增 `AIR_COMPRESSOR_DB_PATH` 環境變數，預設指向 `curated_fastmcp_sqlite_teaching_case/data/air_compressor_teaching_cases.sqlite`。

## Phase 2 - FastMCP SQLite Data Layer

- [ ] 在 `curated_fastmcp_sqlite_teaching_case/fastmcp_stats_agent/server.py` 新增 SQLite 連線層。
- [ ] DB 路徑解析順序：
  - `AIR_COMPRESSOR_DB_PATH`
  - `server.py` 相對路徑 `../data/air_compressor_teaching_cases.sqlite`
  - 明確傳入的 `db_path`
- [ ] 新增 DB health tool：
  - `database_health()`
  - 回傳 DB path、是否存在、cases 筆數、觀測表是否存在、每個 case row count。
- [ ] 新增 case metadata tools：
  - `list_cases()`
  - `get_case_overview(case_id: str)`
  - `get_recommended_checks(case_id: str)`
  - `get_case_events(case_id: str)`
- [ ] 新增安全的 case dataframe loader：
  - 只能從 `cases.observation_table` 白名單取得資料表名稱。
  - 不允許使用者直接傳 arbitrary SQL table name。
  - 使用 `pandas.read_sql_query()` 讀取 SQLite。
- [ ] 保留現有 CSV tools 的相容性，或以新工具命名避免破壞既有教材。

## Phase 3 - MCP Statistical Tools

- [ ] 將現有 CSV 版 `describe_dataset` 改成可支援 SQLite case：
  - 建議新增 `describe_case(case_id: str, time_col: str = "timestamp")`
- [ ] 新增或改造 `baseline_profile`：
  - 支援 `case_id`
  - 支援 `value_col`
  - 支援 `baseline_rows`
- [ ] 新增或改造 `rolling_anomaly_scan`：
  - 支援 `case_id`
  - 支援 `time_col`
  - 支援 `value_col`
  - 支援 `window` 與 `z_threshold`
- [ ] 新增或改造 `group_compare`：
  - 支援 `case_id`
  - 支援 `group_col`
  - 支援 `value_col`
- [ ] 新增或改造 `correlation_report`：
  - 支援 `case_id`
  - 支援 `value_cols`
- [ ] 工具回傳格式需包含：
  - `case_id`
  - `tool_name`
  - `input_arguments`
  - `summary`
  - `evidence`
  - `warnings`

## Phase 4 - Scenario MCP Tools

- [ ] 新增 `analyze_autonomous_sensing(case_id: str = "case_01")`。
  - 依序呼叫或重用：`describe_case`、`baseline_profile`、`rolling_anomaly_scan`、`correlation_report`。
  - 重點欄位：`vibration_mm_s`、`discharge_temp_c`、`motor_current_a`、`pressure_bar`。
  - 回傳：異常狀態、最早異常時間、共同偏移訊號、可能原因、建議檢查部位。
- [ ] 新增 `analyze_night_leakage(case_id: str = "case_02")`。
  - 依序呼叫或重用：`describe_case`、`group_compare`、`rolling_anomaly_scan`、`correlation_report`。
  - 重點欄位：`production_flag`、`flow_m3_min`、`power_kw`、`pressure_bar`。
  - 回傳：是否疑似夜間漏氣、非生產流量/功率差異、最早異常夜間時段、管理建議。
- [ ] 新增 `build_shift_handover(case_id: str = "case_06")`。
  - 使用 `case_events` 與觀測資料找重複異常。
  - 重點欄位：`pressure_bar`、`discharge_temp_c`、`power_kw`、`flow_m3_min`、`dryer_dew_point_c`。
  - 回傳：優先追查時段、重複模式、可觀察項目、交班摘要。
- [ ] 將三個 scenario tools 的輸出固定為繁體中文可交付摘要，同時保留 JSON evidence 給 backend/frontend 顯示。
- [ ] 對 `case_03` 命名做決策：
  - 選項 A：UI 顯示「案例 3 自動交班」，backend 實際使用 `case_06`。
  - 選項 B：重建 SQLite，將 `case_06` 重新命名或複製為 `case_03`。

## Phase 5 - Stdio MCP Server Verification

- [ ] 建立 stdio config：
  - command: repo `.venv/bin/python`
  - args: `curated_fastmcp_sqlite_teaching_case/fastmcp_stats_agent/server.py`
  - cwd: `curated_fastmcp_sqlite_teaching_case`
  - env: `PYTHONPATH` 與 `AIR_COMPRESSOR_DB_PATH`
- [ ] 用 `fastmcp.Client(CONFIG)` 測試 stdio 連線。
- [ ] 測試 `database_health()` 回傳 three cases ready。
- [ ] 測試 `describe_case("case_01")` 回傳 2160 rows。
- [ ] 測試 `analyze_autonomous_sensing()` 有最早異常時間與 evidence。
- [ ] 測試 `analyze_night_leakage()` 有 production/non-production 比較。
- [ ] 測試 `build_shift_handover()` 有重複異常摘要。
- [ ] 將以上測試寫入 `fastmcp_stats_agent/test_sqlite_stdio_config.py`。

## Phase 6 - Bridge MCP Into `main.py`

- [ ] 在 `main.py` 匯入 Agents SDK MCP classes：
  - `from agents.mcp import MCPServerStdio`
- [ ] 建立 MCP server factory，例如 `create_air_compressor_mcp_server()`。
- [ ] 在 agent lifecycle 中：
  - `await mcp_server.connect()`
  - 建立 `Agent(..., mcp_servers=[mcp_server])`
  - `Runner.run(...)`
  - `await mcp_server.cleanup()`
- [ ] 設定 `cache_tools_list=True`，降低每次對話列工具的延遲。
- [ ] 更新 agent instructions：
  - 空壓機案例問題必須先使用 MCP tools。
  - Case 01 使用 autonomous sensing 流程。
  - Case 02 使用 night leakage 流程。
  - 自動交班使用 shift handover 流程。
  - 回覆必須用繁體中文，並包含異常狀態、證據、建議下一步。
- [ ] 保留既有 RAG tools，讓 agent 可以同時查教材與用 MCP 算資料。
- [ ] 加入 fallback 行為：
  - MCP server 無法啟動時，回報具體錯誤。
  - DB health 失敗時，不讓 agent 憑空判斷。

## Phase 7 - Python Backend

- [ ] 建立 backend 目錄，例如 `backend/`。
- [ ] 建議檔案：
  - `backend/app.py`：FastAPI app 與路由。
  - `backend/agent_service.py`：封裝 OpenAI agent、MCP lifecycle、Runner.run。
  - `backend/memory.py`：session memory 與 user memory。
  - `backend/schemas.py`：Pydantic request/response models。
  - `backend/settings.py`：路徑、模型、DB、MCP 設定。
- [ ] 啟動時執行：
  - SQLite health check。
  - MCP stdio health check。
  - agent tool list check。
- [ ] 支援 streaming 或先做 non-streaming：
  - 第一版建議先做 `POST /api/chat` non-streaming。
  - 第二版再加 `POST /api/chat/stream`。
- [ ] 統一錯誤格式：
  - `error_code`
  - `message`
  - `details`
  - `retryable`

## Phase 8 - API Design

- [ ] `GET /api/health`
  - 回傳 backend、SQLite、MCP、agent 狀態。
- [ ] `GET /api/cases`
  - 回傳 case list、title、row_count、time_range、analysis_focus。
- [ ] `GET /api/cases/{case_id}`
  - 回傳單一案例 metadata、events summary、recommended checks。
- [ ] `POST /api/chat`
  - Request:
    - `session_id`
    - `message`
    - `case_id`
    - `use_memory`
  - Response:
    - `session_id`
    - `answer`
    - `tool_calls`
    - `evidence`
    - `suggested_next_actions`
- [ ] `GET /api/sessions`
  - 回傳既有聊天 session 列表。
- [ ] `GET /api/sessions/{session_id}/messages`
  - 回傳 session 對話歷史。
- [ ] `DELETE /api/sessions/{session_id}`
  - 清除單一 session。
- [ ] `GET /api/memory`
  - 回傳 user memory notes。
- [ ] `POST /api/memory`
  - 新增使用者指定記憶，例如偏好的輸出格式、常用場域、課堂角色。
- [ ] `DELETE /api/memory/{memory_id}`
  - 刪除單筆 memory。

## Phase 9 - Memory Plan

- [ ] 使用 Agents SDK 內建 `SQLiteSession` 作為聊天 session memory。
- [ ] 建議 memory DB：
  - `data/agent_memory.sqlite`
- [ ] 建議 tables：
  - `agent_sessions`
  - `agent_messages`
  - `user_memory`
- [ ] `user_memory` 欄位：
  - `id`
  - `scope`
  - `key`
  - `value`
  - `created_at`
  - `updated_at`
- [ ] 每次 `POST /api/chat`：
  - 根據 `session_id` 載入 `SQLiteSession`。
  - 注入 user memory 摘要到 agent instructions 或 input context。
  - 將使用者訊息與 agent 回覆寫入 session。
- [ ] 提供清除 memory 的 API，避免 demo 時舊資料影響判斷。

## Phase 10 - Frontend Chat Interface

- [ ] 建立 `frontend/` 或 `static/`。
- [ ] 第一版可用無 build step 的 HTML/CSS/JS，由 FastAPI serve static files。
- [ ] 主要畫面：
  - 左側：案例選擇與 DB/MCP 狀態。
  - 中間：聊天訊息。
  - 右側：工具證據、異常時間、推薦下一步。
- [ ] Case selector：
  - Case 01 自主感測
  - Case 02 智慧監控
  - 任務 3 自動交班 / backend `case_06`
- [ ] Memory UI：
  - 顯示目前 session id。
  - 新增 memory note。
  - 查看/刪除 memory note。
  - 清除目前 session。
- [ ] Chat UX：
  - loading 狀態。
  - tool call 摘要。
  - 錯誤訊息。
  - retry button。
  - 複製摘要 button。
- [ ] 不在 UI 裡寫過多操作說明，讓介面靠清楚控制與狀態呈現。

## Phase 11 - Tests And Acceptance Criteria

- [ ] `python -m py_compile main.py rag_agent_tools.py curated_fastmcp_sqlite_teaching_case/fastmcp_stats_agent/server.py`
- [ ] SQLite smoke tests 通過。
- [ ] FastMCP direct client tests 通過。
- [ ] FastMCP stdio tests 通過。
- [ ] `main.py` 可啟動 MCP server 並讓 agent 呼叫 MCP tools。
- [ ] Backend `GET /api/health` 回傳 SQLite/MCP ready。
- [ ] Backend `POST /api/chat` 對三個任務都能得到繁體中文答案。
- [ ] Memory session 可跨兩次請求保留上下文。
- [ ] Frontend 可完成一輪聊天、切換案例、新增 memory、清除 session。
- [ ] 錯誤情境可讀：
  - DB missing
  - MCP dependency missing
  - MCP stdio startup failed
  - OpenAI API key missing

## Suggested Additions

- [ ] 新增 `AGENTS.md` 或 `agent.md`，明確規定空壓機案例必須先用 FastMCP 工具，不可直接猜測。
- [ ] 將 SQLite schema 與 MCP tool output 寫成短文件，方便課堂展示。
- [ ] 增加 `database_health()` 到 UI health panel，讓學生看到 agent 不是直接憑空回答。
- [ ] 為 scenario tools 增加 deterministic smoke test，不依賴 LLM，只驗證工具輸出有 evidence。
- [ ] 將 `case_06` 與「案例 3 自動交班」的命名做成常數 mapping，避免前後端各自硬寫。
- [ ] 保留 raw CSV fallback，但正式 agent 流程以 SQLite 為準。
- [ ] 加入 tracing/logging，記錄每次 chat 使用了哪些 MCP tools、輸入參數與摘要結果。

## Immediate Next Implementation Order

1. 補 `.venv` dependency：安裝 `fastmcp`，並補 backend 所需套件。
2. 在 `server.py` 新增 `database_health()`，先讓 FastMCP 能讀 SQLite。
3. 修正 stdio config 與測試，確認 MCP server 能透過 stdio 啟動。
4. 新增三個 scenario tools。
5. 將 `main.py` 接上 `MCPServerStdio`。
6. 建立 FastAPI backend 與 memory。
7. 建立 frontend chat UI。
