# 空壓機 FastMCP + SQLite 教學包

這個資料夾是一個整理好的課堂範例。它把幾份空壓機運轉資料、FastMCP 統計工具、SQLite 資料庫和教學文件放在一起，方便示範 AI agent 不是直接猜答案，而是先查資料、用工具驗證，再整理成現場看得懂的摘要。

白話一點說，這包東西可以用來教三件事：

1. 原始 CSV 資料怎麼整理成 SQLite。
2. AI agent 怎麼用 FastMCP 工具先做統計檢查。
3. 統計結果怎麼變成維修、監控、交班用的繁體中文結論。

## 這包資料是什麼

這裡選了三個資料比較完整、也比較適合教學的案例：

| 案例 | 資料性質 | 可以教什麼 |
| --- | --- | --- |
| Case 01 自主感測 | 2160 筆，每 10 分鐘一筆，記錄壓力、排氣溫度、振動、馬達電流 | 教學生看多個感測訊號是否一起偏離，判斷可能的機械異常 |
| Case 02 智慧監控 | 360 筆，每小時一筆，記錄是否生產、流量、功率、壓力 | 教學生比較生產中與非生產時段，判斷夜間漏氣或用氣浪費 |
| Case 06 自動交班 | 480 筆，巡檢式資料，記錄壓力、溫度、功率、流量、乾燥機露點 | 教學生把重複異常整理成交班摘要 |

每個案例都有兩種資料：

- 觀測資料：像現場感測器或巡檢系統留下來的時間序列紀錄。
- 異常標記：資料產生時有刻意放入一些異常事件，例如冷卻問題、夜間漏氣、低壓、乾燥機露點偏高。這些標記可以拿來對照 AI agent 有沒有抓到重點。

## 這些資料的作用

這包資料不是要直接拿去控制設備，而是用來做教學與展示。

它適合拿來示範：

- 怎麼把分散的 CSV 檔整理成一個 SQLite。
- 怎麼用 SQL 快速看資料範圍、筆數、異常事件分布。
- 怎麼讓 FastMCP 幫 AI agent 做基準值、群組比較、異常掃描、相關性分析。
- 怎麼把工具結果轉成「現場主管、維修人員、交班人員看得懂」的結論。

最後學生應該能回答：

- 哪個時間最值得注意？
- 哪個訊號支持這個判斷？
- 可能是什麼原因？
- 下一步要查什麼或做什麼？

## 跑完會得到什麼成果

目前已經整理好一個 SQLite：

```text
data/air_compressor_teaching_cases.sqlite
```

這個資料庫裡有：

- 三張主要觀測資料表，分別放 Case 01、Case 02、Case 06。
- 一張案例總表，記錄每個案例的資料量、時間範圍和教學重點。
- 一張異常事件表，整理 manifest 裡的注入異常。
- 一張 FastMCP 推薦檢查表，告訴學生每個案例應該先用哪些工具。
- 一張 FastMCP 重點發現表，放這次已經用工具驗證過的代表結果。
- 幾個 view，讓課堂上可以快速查總覽和異常列。

例如查案例總覽會看到：

| case_id | 資料筆數 | 時間範圍 | 事件數 |
| --- | ---: | --- | ---: |
| case_01 | 2160 | 2026-05-01 00:00 到 2026-05-15 23:50 | 8 |
| case_02 | 360 | 2026-05-01 00:00 到 2026-05-15 23:00 | 5 |
| case_06 | 480 | 2026-05-01 08:00 到 2026-05-15 15:45 | 12 |

## 程式需要做什麼功能

這個教學包裡的程式主要分成兩部分。

第一部分是 SQLite 建置：

```text
scripts/build_sqlite.py
```

它負責：

- 讀取 `raw_data/` 裡的 CSV。
- 自動判斷欄位型態，例如時間、數字、文字。
- 建立 SQLite 資料表。
- 匯入三個案例的觀測資料。
- 讀取 manifest，整理異常事件。
- 建立教學用 view。
- 寫入 FastMCP 推薦檢查步驟和已驗證重點。

第二部分是 FastMCP 統計工具：

```text
fastmcp_stats_agent/server.py
```

它提供 AI agent 可以呼叫的工具：

- `describe_dataset`：確認資料筆數、欄位、缺值、時間範圍。
- `baseline_profile`：計算前幾筆或早期資料的基準值。
- `group_compare`：比較不同群組，例如生產中和非生產時段。
- `rolling_anomaly_scan`：用 rolling z-score 找異常時間點。
- `correlation_report`：看多個訊號是否一起變動。

## 資料夾內容

```text
raw_data/
  三個案例的原始 CSV、manifest、任務腳本與 guide

fastmcp_stats_agent/
  FastMCP 統計工具與 MCP 設定樣板

data/
  air_compressor_teaching_cases.sqlite

scripts/
  build_sqlite.py

docs/
  teaching_case.md
  classroom_material.md
  schema.sql

sql/
  classroom_queries.sql
```

更完整的課堂教材文件請看：

```text
docs/classroom_material.md
```

這份文件包含教學目標、資料性質、程式功能、SQL 運行結果、FastMCP 運行結果、範例交付答案與延伸練習。

## 快速使用

重建 SQLite：

```bash
python3 scripts/build_sqlite.py
```

查看案例總覽：

```bash
sqlite3 -header -column data/air_compressor_teaching_cases.sqlite \
  "select * from v_case_overview;"
```

查看異常事件：

```bash
sqlite3 -header -column data/air_compressor_teaching_cases.sqlite \
  "select * from v_all_anomaly_events order by start_time limit 20;"
```

查看每個案例建議先呼叫哪些 FastMCP 工具：

```bash
sqlite3 -header -column data/air_compressor_teaching_cases.sqlite \
  "select case_id, step_order, tool_name, purpose from fastmcp_recommended_checks order by case_id, step_order;"
```

## 建議教學流程

1. 先用 SQL 看 `v_case_overview`，讓學生知道資料量、時間範圍和事件數。
2. 再查 `v_anomaly_rows` 或 `v_all_anomaly_events`，讓學生知道異常大概在哪裡。
3. 查 `fastmcp_recommended_checks`，決定每個案例要先用哪個 FastMCP 工具。
4. 讓 AI agent 呼叫 FastMCP 工具，得到基準值、群組比較、異常掃描或相關性。
5. 最後請學生把工具結果寫成 5 句內的繁體中文摘要。

## 一句話總結

這個教學包的核心是：先把現場資料整理成 SQLite，讓 AI agent 透過 FastMCP 做統計查證，再把證據整理成可以交付給維修、節能或交班現場的結論。
