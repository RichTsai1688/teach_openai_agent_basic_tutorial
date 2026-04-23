# RAG Agent Integration Checklist

## Goal

把 `rag_tools` 已建立好的 RAG 查詢能力匯入目前 `main.py` 的 OpenAI Agents SDK agent，讓 agent 可以透過 `function_tool` 查詢本地 FAISS index。

## Current Status

- [x] `rag_tools` 目錄存在，包含 CLI、核心 runtime、docs、requirements 與 output。
- [x] 已找到預建索引檔：
  - `rag_tools/output/composite_v2.json`
  - `rag_tools/output/composite_v2_index.index`
  - `rag_tools/output/composite_v2_index.pickle`
- [x] `composite_v2.json` 目前有 153 筆資料。
- [x] `composite_v2_index.pickle` mapping 目前有 153 筆 `id_to_text`。
- [x] FAISS index 可載入，`ntotal=153`，`dimension=768`。
- [x] `rag_tools/scripts/test_imports.py` 通過。
- [x] 已安裝 `rag_tools/requirements.txt` 到本專案 `.venv`。

## Important Integration Notes

- 現有 index 維度是 `768`。
- `rag_tools/docs/embedder.json` 裡 OpenAI 預設 embedding 設定是 `text-embedding-3-small` 且 `dimensions=256`，與現有 index 不一致。
- `rag_tools/docs/embedder.json` 裡 Ollama embedding 預設是 `nomic-embed-text`，常見輸出維度是 `768`，看起來比較符合目前 index。
- 查詢時必須使用「建立 index 時相同的 embedding provider/model/dimension」，否則 query embedding 會失敗或回傳空結果。
- `rag_tools/lib/project_config.py` 預設讀取 `rag_tools/.env`，但目前 agent 的 `.env` 在 repo 根目錄。因為 `main.py` 已先 `load_dotenv()`，整合進同一 process 後通常可以讀到根目錄環境變數；若單獨跑 `rag_cli.py`，可能需要補 `rag_tools/.env` 或調整 env loading。
- `main.py` 目前已使用 `ToolSearchTool()`，所以可以安全加入 deferred-loading RAG function tools。

## Proposed Function Tools

- [x] `rag_search(query: str, top_k: int = 5) -> str`
  - 主要給 agent 使用。
  - 載入 `rag_tools/output/composite_v2_index`。
  - 呼叫 `RAGSystem.query(query, top_k)`。
  - 回傳精簡答案與來源清單。

- [x] `rag_retrieve(query: str, top_k: int = 5) -> dict`
  - 可選工具，用於只取 retrieved chunks，不讓 RAGSystem 再呼叫內部 LLM。
  - 適合讓 agent 自己根據檢索結果整合回答。
  - 目前 `RAGSystem.query()` 會同時做 retrieval + LLM answer；若要純 retrieval，建議在 `rag_tools/lib/rag_system.py` 補一個 `retrieve()` 方法。

- [x] `rag_index_status() -> dict`
  - 回報 index 是否存在、是否可載入、vector 數量、維度、資料筆數。
  - 適合 debug 或課堂示範。

## Recommended Implementation Plan

- [x] 新增 `rag_agent_tools.py`
  - 封裝 `sys.path` / import `RAGSystem`。
  - 定義 index 路徑常數。
  - 用 lazy singleton cache RAGSystem，避免每次 tool call 都重載 FAISS。
  - 提供 `@function_tool(defer_loading=True)` 的 `rag_search` 與 `rag_index_status`。

- [x] 更新 `main.py`
  - import `rag_search`, `rag_index_status`。
  - 建立 `rag_tools = tool_namespace(name="rag", description="...")`。
  - agent tools 加入 `*rag_tools`。
  - 保留 `ToolSearchTool()`，因為 RAG tools 也會使用 deferred loading。

- [x] 確認 embedding provider
  - 若 index 是 Ollama 建的：設定 `LLM_PROVIDER=ollama`、`OLLAMA_URL`、`OLLAMA_MODEL`、必要時 `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`。
  - 若要改用 OpenAI：需要用 OpenAI embedding 重新建立 index，並修正 `RAGSystem.get_embedding()` 是否傳入 `dimensions`。

- [x] 加測試/驗證
  - `rag_index_status()` 回傳 `ntotal=153`、`dimension=768`。
  - `rag_search("介紹一下培育對象", top_k=5)` 能回傳答案與來源。
  - `.venv/bin/python main.py` 能讓 agent 呼叫 RAG tool。

## Requirements Installed In `.venv`

Runtime requirements already installed from `rag_tools/requirements.txt`:

- `beautifulsoup4==4.14.3`
- `faiss-cpu==1.13.2`
- `lxml==6.1.0`
- `numpy==2.4.4`
- `openai==2.32.0`
- `pandas==2.3.3`
- `python-dotenv==1.2.2`
- `PyYAML==6.0.3`
- `requests==2.33.1`
- `selenium==4.43.0`
- `sentence-transformers==5.4.1`
- `tqdm==4.67.3`
- `webdriver-manager==4.0.2`

## Verification Results

- [x] `.venv/bin/python -m py_compile main.py rag_agent_tools.py rag_tools/lib/project_config.py rag_tools/lib/rag_system.py`
- [x] `.venv/bin/python rag_tools/scripts/test_imports.py`
- [x] `rag_index_status_impl()` 回傳 `ready=True`、`vectors=153`、`texts=153`、`embedding_dimension=768`。
- [x] `rag_retrieve_impl("介紹一下培育對象", 3)` 可回傳 3 筆 retrieved chunks。
- [x] `rag_search_impl("介紹一下培育對象", 3)` 可回傳 answer 與 sources。
- [x] `.venv/bin/python main.py` 可讓 agent 呼叫本地 RAG tools 並輸出回答。

## Open Questions

- [ x] `composite_v2_index` 當初是用哪個 embedding provider/model 建立？
OPENAI_MODEL=gpt-5.4-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSION=256
- [ x] Agent tool 要回傳「RAGSystem 生成的 answer」，還是只回傳 retrieved chunks 讓 agent 自己回答？
兩個要，建立prompt依據使用者情境來區分
- [ x] 是否要把 `rag_tools/.env` 與 repo 根目錄 `.env` 的載入邏輯統一？
載入邏輯統一
