# 教材文件：用 FastMCP 與 SQLite 教 AI Agent 判讀空壓機資料

## 1. 教材目的

這份教材用一組整理好的空壓機資料，示範 AI agent 如何從「原始設備資料」一路做到「可交付的現場摘要」。

課堂重點不是讓 AI 直接猜答案，而是讓 AI 先完成三件事：

1. 用 SQLite 查資料，確認資料範圍、筆數、異常事件。
2. 用 FastMCP 統計工具檢查基準值、群組差異、異常點與訊號關係。
3. 把查證後的結果寫成維修、節能或交班現場能理解的繁體中文摘要。

## 2. 資料性質

本教材選了三個資料比較完整、教學角色不同的案例。

| 案例 | 資料筆數 | 時間粒度 | 資料性質 | 教學作用 |
| --- | ---: | --- | --- | --- |
| Case 01 自主感測 | 2160 | 每 10 分鐘 | 壓力、排氣溫度、振動、馬達電流 | 訓練 AI 判斷多個感測訊號是否一起異常 |
| Case 02 智慧監控 | 360 | 每小時 | 是否生產、流量、功率、壓力 | 訓練 AI 比較生產與非生產時段，判斷夜間漏氣 |
| Case 06 自動交班 | 480 | 巡檢式時間序列 | 壓力、溫度、功率、流量、乾燥機露點 | 訓練 AI 把重複異常整理成交班摘要 |

資料中包含兩類資訊：

- 觀測資料：模擬現場感測器或巡檢系統的時間序列紀錄。
- 異常標記：資料產生時刻意加入的異常事件，例如冷卻問題、夜間漏氣、低壓、乾燥機露點偏高。

這些異常標記的用途，是讓學生能檢查 AI agent 找到的異常是否接近「已知答案」。

## 3. 教材包結構

```text
raw_data/
  三個案例的原始 CSV、manifest、任務腳本與 guide

fastmcp_stats_agent/
  FastMCP 統計工具

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

## 4. 程式需要具備的功能

### 4.1 SQLite 建置程式

程式位置：

```text
scripts/build_sqlite.py
```

這支程式負責把原始 CSV 與 manifest 整理成 SQLite。它需要具備以下功能：

- 讀取 `raw_data/` 裡的 CSV。
- 自動判斷欄位型態，例如時間、整數、小數、文字。
- 建立三張觀測資料表。
- 匯入 Case 01、Case 02、Case 06 的觀測資料。
- 讀取 manifest，建立異常事件表。
- 建立案例總覽表。
- 建立 FastMCP 推薦檢查表。
- 建立教學用 view，讓學生可以快速查詢總覽與異常資料。

### 4.2 FastMCP 統計工具

程式位置：

```text
fastmcp_stats_agent/server.py
```

它提供 AI agent 呼叫的統計工具：

| 工具 | 作用 |
| --- | --- |
| `describe_dataset` | 看資料筆數、欄位、缺值與時間範圍 |
| `baseline_profile` | 取前幾筆資料建立基準值 |
| `group_compare` | 比較不同群組，例如生產中與非生產時段 |
| `rolling_anomaly_scan` | 用 rolling z-score 找異常時間點 |
| `correlation_report` | 看多個訊號是否一起變動 |

## 5. 實際運行結果

### 5.1 重建 SQLite

執行指令：

```bash
python3 scripts/build_sqlite.py
```

運行結果：

```text
Built SQLite database: /Users/rich-new-mbp/Documents/空壓機演講/air_compressor_ai_agent_case_pack/curated_fastmcp_sqlite_teaching_case/data/air_compressor_teaching_cases.sqlite
```

完整性檢查：

```bash
sqlite3 data/air_compressor_teaching_cases.sqlite 'pragma integrity_check;'
```

結果：

```text
ok
```

代表 SQLite 已可正常讀取，資料庫結構沒有損壞。

### 5.2 案例總覽查詢

執行指令：

```bash
sqlite3 -header -column data/air_compressor_teaching_cases.sqlite \
  "select * from v_case_overview;"
```

運行結果：

```text
case_id  title                                      observation_table               row_count  start_time        end_time          analysis_focus                                                   event_count
-------  -----------------------------------------  ------------------------------  ---------  ----------------  ----------------  ---------------------------------------------------------------  -----------
case_01  Autonomous sensing anomaly diagnosis       case01_sensor_observations      2160       2026-05-01 00:00  2026-05-15 23:50  vibration, discharge temperature, motor current, pressure drift  8
case_02  Smart monitoring and night leakage review  case02_monitoring_observations  360        2026-05-01 00:00  2026-05-15 23:00  production flag, night flow, power, pressure                     5
case_06  Auto logbook and shift handover            case06_logbook_observations     480        2026-05-01 08:00  2026-05-15 15:45  pressure, discharge temperature, power, flow, dryer dew point    12
```

代表意思：

- Case 01 資料最多，適合教高頻感測資料分析。
- Case 02 資料筆數較少但群組清楚，適合教生產/非生產比較。
- Case 06 有多種巡檢異常，適合教交班摘要與異常分類。

### 5.3 異常資料分布

執行指令：

```bash
sqlite3 -header -column data/air_compressor_teaching_cases.sqlite \
  "select case_id, anomaly_type, count(*) as abnormal_rows
   from v_anomaly_rows
   group by case_id, anomaly_type
   order by case_id, abnormal_rows desc;"
```

運行結果：

```text
case_id  anomaly_type      abnormal_rows
-------  ----------------  -------------
case_01  cooling_issue     15
case_01  load_spike        11
case_01  bearing_wear      11
case_01  lubrication_loss  7
case_02  night_leak        96
case_06  low_pressure      20
case_06  cooling_issue     16
case_06  dryer_issue       12
```

代表意思：

- Case 01 有多種類型的機械或操作異常，可訓練多訊號判讀。
- Case 02 的 `night_leak` 有 96 筆，代表夜間漏氣是這題的主要情境。
- Case 06 的低壓最多，其次是冷卻與乾燥機問題，適合做交班重點排序。

### 5.4 Case 02 生產與非生產時段比較

執行指令：

```bash
sqlite3 -header -column data/air_compressor_teaching_cases.sqlite \
  "select
     production_flag,
     count(*) as rows,
     round(avg(flow_m3_min), 4) as avg_flow_m3_min,
     round(avg(power_kw), 4) as avg_power_kw,
     round(avg(pressure_bar), 4) as avg_pressure_bar
   from case02_monitoring_observations
   group by production_flag;"
```

運行結果：

```text
production_flag  rows  avg_flow_m3_min  avg_power_kw  avg_pressure_bar
---------------  ----  ---------------  ------------  ----------------
0                180   1.1164           17.329        6.9381
1                180   7.7943           48.6388       7.0621
```

代表意思：

- `production_flag=0` 是非生產時段，理論上流量應該低，但平均仍有 1.1164 m3/min。
- 非生產時段平均功率仍有 17.329 kW，代表即使沒生產，空壓系統仍在消耗能量。
- 這可以引導學生判斷是否有夜間漏氣、閥件未關、或合法用氣未標記。

### 5.5 Case 06 高露點窗口

執行指令：

```bash
sqlite3 -header -column data/air_compressor_teaching_cases.sqlite \
  "select
     timestamp,
     dryer_dew_point_c,
     pressure_bar,
     discharge_temp_c,
     power_kw,
     flow_m3_min,
     anomaly_event_id,
     anomaly_type
   from case06_logbook_observations
   where dryer_dew_point_c >= 7.0
   order by timestamp
   limit 12;"
```

運行結果：

```text
timestamp         dryer_dew_point_c  pressure_bar  discharge_temp_c  power_kw  flow_m3_min  anomaly_event_id  anomaly_type
----------------  -----------------  ------------  ----------------  --------  -----------  ----------------  ------------
2026-05-09 10:00  7.92               7.05          87.6              31.93     6.64         LOG-08            dryer_issue
2026-05-09 10:15  7.72               7.04          87.17             32.03     6.87         LOG-08            dryer_issue
2026-05-09 10:30  7.65               7.05          87.63             32.44     6.74         LOG-08            dryer_issue
2026-05-09 10:45  7.85               7.04          88.01             32.56     7.01         LOG-08            dryer_issue
2026-05-13 11:00  7.8                7.06          88.19             32.47     7.04         LOG-10            dryer_issue
2026-05-13 11:15  7.69               7.05          88.03             33.02     6.73         LOG-10            dryer_issue
2026-05-13 11:30  7.9                7.04          88.66             33.38     6.86         LOG-10            dryer_issue
2026-05-13 11:45  7.97               7.05          88.56             33.2      7.07         LOG-10            dryer_issue
2026-05-14 09:00  7.69               7.0           85.92             30.36     6.24         LOG-12            dryer_issue
2026-05-14 09:15  7.78               7.03          86.3              30.83     6.32         LOG-12            dryer_issue
2026-05-14 09:30  7.96               7.04          86.81             31.85     6.5          LOG-12            dryer_issue
2026-05-14 09:45  7.97               7.04          86.56             31.29     6.52         LOG-12            dryer_issue
```

代表意思：

- 乾燥機露點在 2026-05-09、2026-05-13、2026-05-14 都出現高值。
- 這些列都被標成 `dryer_issue`，表示乾燥機問題適合列入交班提醒。
- 現場下一步可檢查乾燥機再生、排水、入口溫度與濾芯狀態。

## 6. FastMCP 運行結果

### 6.1 Case 01 自主感測

FastMCP `describe_dataset` 結果：

```text
rows: 2160
time_range: 2026-05-01 00:00 to 2026-05-15 23:50
columns: timestamp, pressure_bar, discharge_temp_c, vibration_mm_s, motor_current_a, is_injected_anomaly, anomaly_event_id, anomaly_type
missing sensor values: 0
```

FastMCP `baseline_profile` 檢查 `vibration_mm_s` 前 24 筆：

```text
mean: 2.0722
std: 0.0549
median: 2.0849
min: 1.9722
max: 2.1657
```

FastMCP `correlation_report` 顯示：

```text
discharge_temp_c vs vibration_mm_s: 0.78
discharge_temp_c vs motor_current_a: 0.7686
motor_current_a vs vibration_mm_s: 0.6585
discharge_temp_c vs pressure_bar: -0.5821
```

判讀：

Case 01 的異常不適合只看單一振動數值，因為振動、排氣溫度、馬達電流有明顯同向關係。若振動與溫度一起升高，現場應優先檢查軸承、潤滑、冷卻與負載變化。

### 6.2 Case 02 智慧監控

FastMCP `group_compare` 檢查 `production_flag` 與流量：

```text
production_flag=0: count=180, mean flow=1.1164
production_flag=1: count=180, mean flow=7.7943
```

FastMCP `group_compare` 檢查 `production_flag` 與功率：

```text
production_flag=0: count=180, mean power=17.329
production_flag=1: count=180, mean power=48.6388
```

判讀：

非生產時段仍有流量與功率，代表不是單純停機狀態。若現場沒有合法夜間用氣，這很適合當作夜間漏氣偵測與節能改善案例。

### 6.3 Case 06 自動交班

FastMCP `rolling_anomaly_scan` 檢查 `dryer_dew_point_c`：

```text
flag_count: 12
first_flag: 2026-05-04 14:45
top high flags:
2026-05-09 10:00, value=7.92, z_score=4.719
2026-05-09 10:15, value=7.72, z_score=3.213
2026-05-09 10:30, value=7.65, z_score=2.559
2026-05-13 11:00, value=7.8, z_score=4.67
```

判讀：

Case 06 的乾燥機露點異常有明確重複時段，適合讓 AI agent 產生交班摘要。摘要不應只說「露點異常」，還應指出具體時間、連續性、是否和功率或流量一起升高。

## 7. 課堂操作流程

### Step 1：確認資料庫可用

```bash
python3 scripts/build_sqlite.py
sqlite3 data/air_compressor_teaching_cases.sqlite 'pragma integrity_check;'
```

學生應確認結果為 `ok`。

### Step 2：用 SQL 看資料總覽

```sql
select * from v_case_overview;
```

學生應回答：

- 哪個案例資料最多？
- 每個案例的時間範圍是多少？
- 每個案例有幾個異常事件？

### Step 3：用 SQL 找異常分布

```sql
select
  case_id,
  anomaly_type,
  count(*) as abnormal_rows
from v_anomaly_rows
group by case_id, anomaly_type
order by case_id, abnormal_rows desc;
```

學生應回答：

- Case 01 最常見的異常類型是什麼？
- Case 02 是否主要是夜間漏氣？
- Case 06 哪一類異常最常進入交班？

### Step 4：用 FastMCP 查證

學生不要直接寫結論，應先照 `fastmcp_recommended_checks` 呼叫工具。

```sql
select
  case_id,
  step_order,
  tool_name,
  arguments_json,
  purpose
from fastmcp_recommended_checks
order by case_id, step_order;
```

### Step 5：寫成現場摘要

學生最後輸出 5 句內繁體中文摘要，格式如下：

```text
主要異常：
最值得注意的時間：
支撐判斷的訊號：
可能原因：
下一步建議：
```

## 8. 範例交付答案

### Case 01 範例

主要異常是多訊號共同偏離，振動、排氣溫度與馬達電流都有連動跡象。最值得注意的是 manifest 第一個注入事件 2026-05-03 12:10 到 12:40，且 FastMCP 顯示振動與排氣溫度相關係數為 0.78。這代表異常可能不是單一感測雜訊，而是機械摩擦、冷卻或負載變化造成。下一步建議檢查軸承、潤滑狀態、冷卻效率與馬達電流是否同步升高。

### Case 02 範例

主要異常是非生產時段仍有明顯流量與功率消耗。`production_flag=0` 時平均流量為 1.1164 m3/min、平均功率為 17.329 kW，代表夜間或停線時仍有用氣負載。若現場沒有合法夜間用氣，這很可能是漏氣、閥件未關或旁通用氣造成。下一步建議比對夜間用氣許可、巡檢漏氣點與區域閥件狀態。

### Case 06 範例

主要異常是乾燥機露點在多個時段重複偏高。最值得注意的是 2026-05-09 10:00、2026-05-13 11:00 與 2026-05-14 09:00 前後，露點都高於 7 C，且標記為 `dryer_issue`。這代表乾燥機處理能力或排水、再生流程可能不穩。下一步建議交班時提醒檢查乾燥機再生、排水、入口溫度與濾芯壓差。

## 9. 教師講解重點

- SQL 負責快速整理資料範圍與已知事件。
- FastMCP 負責提供可重複的統計證據。
- AI agent 負責把統計證據翻譯成現場可用的判斷與建議。
- 好的 AI 摘要應該有時間、訊號、理由與下一步，而不是只說「發現異常」。

## 10. 延伸練習

1. 加入 Case 07 多機排程資料，讓學生練習 demand、tariff、line pressure 的排程判斷。
2. 加入 Case 08 漏氣派工資料，讓學生練習 zone 優先順序與修後驗證。
3. 讓學生新增 `student_notes` 表，把自己的 FastMCP 結果與摘要存回 SQLite。
4. 改寫 `build_sqlite.py`，讓 FastMCP 工具輸出自動寫入 `fastmcp_findings`。
