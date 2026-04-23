# MCP 設定樣板

這個資料夾提供兩種內容：

- `*.template.json`：給學生複製後自行修改路徑的樣板
- `generated/*.local.json`：依照目前這個專案路徑自動生成、可直接使用的本地設定檔

## 你會看到哪些檔案
- `mcpServers.template.json`
- `claude_desktop_config.template.json`
- `generated/mcpServers.local.json`
- `generated/claude_desktop_config.local.json`

## 如何產生本地設定檔
```bash
./.venv/bin/python fastmcp_stats_agent/generate_mcp_configs.py
```

## 如何使用

### 通用 `mcpServers` 設定
把 `generated/mcpServers.local.json` 的內容複製到支援 `mcpServers` 格式的客戶端設定檔。

### Claude Desktop
把 `generated/claude_desktop_config.local.json` 的內容合併到你的 `claude_desktop_config.json`。

## 如何和 Codex 一起用
1. 先完成 MCP 設定
2. 再確認專案根目錄有：
   - [AGENTS.md](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/AGENTS.md)
   - [agent.md](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/agent.md)
3. 讓 Codex 在這個專案目錄中工作
4. 再依照：
   - [學生流程](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/student_workflow.md)
   - 各題 `advance/agent_task_script.md`
   去呼叫工具與整理摘要

如果你是第一次操作，先看：
- [FastMCP 架設與 Codex 連接教學](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/setup_fastmcp_codex_tutorial.md)

## 如果要給學生發模板
請讓學生修改這兩個欄位：
- `command`
- `args`

若學生的專案路徑不同，也要同步調整：
- `cwd`
- `env.PYTHONPATH`
