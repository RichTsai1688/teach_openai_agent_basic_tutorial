# FastMCP 架設與 Codex 連接教學

這份教學是給第一次接觸 FastMCP 與 Codex 的同學使用。  
目標是把本專案的統計工具架起來，並讓 Codex 進到專案後就知道該怎麼用。

## 你會做到什麼
1. 建立 `.venv`
2. 安裝套件
3. 啟動 FastMCP server
4. 產生 MCP 設定檔
5. 讓 Codex 讀到這個專案的 `AGENTS.md` / `agent.md`

## Step 1：建立虛擬環境
```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Step 2：確認 FastMCP server 可以啟動
```bash
./.venv/bin/python fastmcp_stats_agent/server.py
```

正常情況下，這個指令會讓 FastMCP server 進入等待狀態。  
如果只是測試能不能啟動，看到程式成功跑起來後可以用 `Ctrl + C` 停掉。

## Step 3：產生本機 MCP 設定檔
```bash
./.venv/bin/python fastmcp_stats_agent/generate_mcp_configs.py
```

執行後會產生：
- `fastmcp_stats_agent/mcp_configs/generated/mcpServers.local.json`
- `fastmcp_stats_agent/mcp_configs/generated/claude_desktop_config.local.json`

## Step 4：把設定接到支援 MCP 的客戶端

### 如果你的客戶端支援 `mcpServers`
把下面這份內容貼到客戶端設定檔：
- [mcpServers.local.json](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/mcp_configs/generated/mcpServers.local.json)

### 如果你是用 Claude Desktop
把下面這份內容合併到 `claude_desktop_config.json`：
- [claude_desktop_config.local.json](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/mcp_configs/generated/claude_desktop_config.local.json)

更多格式說明可看：
- [MCP 設定樣板說明](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/mcp_configs/README.md)

## Step 5：讓 Codex 讀到專案指引
這個專案根目錄已經放好兩份指引：
- [AGENTS.md](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/AGENTS.md)
- [agent.md](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/agent.md)

用途很簡單：
- 告訴 Codex 先用 FastMCP 工具，不要一開始就直接猜答案
- 告訴 Codex 先看哪份流程文件
- 告訴 Codex 最後要整理成什麼樣的摘要

## Step 6：實際開一題來練
建議先選一題有 `advance/agent_task_script.md` 的案例，例如：
- [Case 07 Agent 任務腳本](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/case_07_multi_compressor_scheduling_agent/advance/agent_task_script.md)
- [Case 08 Agent 任務腳本](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/case_08_leak_detection_dispatch_agent/advance/agent_task_script.md)
- [Case 09 Agent 任務腳本](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/case_09_lights_out_shift_agent/advance/agent_task_script.md)

也可以先看總流程：
- [學生流程](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/student_workflow.md)

## 學生最常用的問法
```text
請先不要直接下結論，先用 FastMCP 統計工具查證這份資料。
先描述資料，再找基準值或群組差異，再掃描異常，最後用繁體中文整理成 5 句摘要。
```

## 如果啟動不起來，先檢查這幾件事
1. `.venv` 是否在專案根目錄
2. `requirements.txt` 是否已安裝完成
3. `generate_mcp_configs.py` 產出的路徑是否和你的專案位置一致
4. 客戶端設定中的 `command`、`args`、`cwd`、`PYTHONPATH` 是否正確

## 最後要記得
真正重要的不是把工具架起來而已，而是：
- 先查資料
- 再查統計
- 最後才做判讀

這樣做出來的 AI Agent 才會比較像真的分析流程。
