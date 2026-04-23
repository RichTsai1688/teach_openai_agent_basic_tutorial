# FastMCP 統計工具箱

這個資料夾提供一個簡單的 `FastMCP` 伺服器，讓 AI Agent 可以先呼叫統計工具，再根據結果做解讀。

## 這個工具箱適合做什麼
- 檢查資料欄位、缺值與時間範圍
- 計算基準值、標準差、中位數、MAD、IQR
- 掃描 rolling z-score 異常
- 比較不同群組的平均值與分布
- 建立相關係數表，找出可能一起變動的訊號

## 為什麼這樣更像 AI Agent
在 AI-agent 流程裡，AI 不一定直接硬判斷。  
比較合理的做法是：
1. 先呼叫統計工具
2. 拿到數字與指標
3. 再用自然語言解釋成結論、風險與建議

## 安裝
請先安裝需求套件：

```bash
./.venv/bin/pip install -r requirements.txt
```

如果你是第一次架 FastMCP，建議先看：
- [FastMCP 架設與 Codex 連接教學](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/setup_fastmcp_codex_tutorial.md)

## 啟動
```bash
./.venv/bin/python fastmcp_stats_agent/server.py
```

## MCP 設定樣板
已提供：
- [MCP 設定說明](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/mcp_configs/README.md)
- [通用模板](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/mcp_configs/mcpServers.template.json)
- [Claude Desktop 模板](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/mcp_configs/claude_desktop_config.template.json)

如果要直接產生這台機器可用的設定檔：

```bash
./.venv/bin/python fastmcp_stats_agent/generate_mcp_configs.py
```

## Codex 指引檔
這個專案根目錄已放好給 Codex 使用的指引檔：
- [AGENTS.md](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/AGENTS.md)
- [agent.md](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/agent.md)

這兩份檔案會提醒 Codex：
- 先用 FastMCP 工具
- 再看學生流程與案例腳本
- 最後整理成可交付摘要

## 建議的課堂流程
1. 先讓 AI 讀案例資料
2. 讓 AI 呼叫統計工具，例如：
   - `describe_dataset`
   - `baseline_profile`
   - `rolling_anomaly_scan`
   - `group_compare`
   - `correlation_report`
3. 再請 AI 根據工具輸出整理成：
   - 結論
   - 異常時段
   - 可能原因
   - 建議行動

如果你要直接照案例練，學生流程頁已經整理到 `case_01 ~ case_09`：
- [學生流程](/Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/fastmcp_stats_agent/student_workflow.md)

## 範例問法
```text
請先使用統計工具找出這份資料的基準值、離群點與最近異常變化，再整理成 5 句重點摘要。
```
