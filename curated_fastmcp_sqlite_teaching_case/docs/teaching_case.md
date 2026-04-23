# 教學案例：FastMCP + SQLite 空壓機資料判讀

## 案例定位

這個教學案例把三個進階資料集整理成同一個 SQLite，目標是讓學生練習「先查資料、再用 FastMCP 驗證、最後寫成可交付摘要」。

選入案例：

| 案例 | 資料量 | 教學重點 |
| --- | ---: | --- |
| Case 01 自主感測 | 2160 筆 | 振動、排氣溫度、馬達電流與壓力的多訊號異常判讀 |
| Case 02 智慧監控 | 360 筆 | 產線/非產線流量與功率差異，判斷夜間漏氣或合法用氣 |
| Case 06 自動交班 | 480 筆 | 壓力、排氣溫度、功率、流量、乾燥機露點的交班摘要 |

## 學習目標

- 用 SQL 先確認資料規模、時間範圍與異常事件分布。
- 用 FastMCP 的 `describe_dataset`、`baseline_profile`、`group_compare`、`rolling_anomaly_scan`、`correlation_report` 查證，不直接猜結論。
- 比較「manifest 注入異常」與「rolling anomaly 早期旗標」的差異。
- 將統計結果整理成現場可讀的繁體中文維修、監控或交班摘要。

## 快速任務

### Step 1：資料總覽

```sql
select * from v_case_overview;
```

學生應先指出：

- 哪個案例資料最多。
- 每個案例的時間範圍。
- 每個案例有多少注入事件。
- 三個案例各適合訓練哪一種 AI agent 任務。

### Step 2：找出異常事件分布

```sql
select
  case_id,
  anomaly_type,
  count(*) as abnormal_rows
from v_anomaly_rows
group by case_id, anomaly_type
order by case_id, abnormal_rows desc;
```

引導問題：

- Case 01 的機械異常是溫度、振動、負載，還是潤滑問題較多？
- Case 02 的夜間漏氣有幾天連續出現？
- Case 06 的低壓、冷卻、乾燥機露點問題，哪一類最常進入交班？

### Step 3：照推薦清單呼叫 FastMCP

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

學生依清單呼叫 FastMCP，再把工具結果填回摘要。重點不是一次把所有答案寫完，而是先用工具建立證據鏈。

## 已驗證重點

### Case 01：自主感測異常

FastMCP 顯示資料為 2160 筆，時間範圍是 2026-05-01 00:00 到 2026-05-15 23:50，感測欄位沒有缺值。前 24 筆 `vibration_mm_s` 基準平均為 2.0722 mm/s，rolling scan 最早在 2026-05-01 06:30 出現振動旗標，但 manifest 中第一個注入事件從 2026-05-03 12:10 開始。振動與排氣溫度相關係數 0.78，排氣溫度與馬達電流相關係數 0.7686，表示異常摘要應同時觀察機械摩擦、冷卻與電流負載。

### Case 02：智慧監控與夜間漏氣

FastMCP 顯示資料為 360 筆，產線與非產線各 180 筆。`production_flag=0` 的平均流量為 1.1164 m3/min、平均功率為 17.329 kW；`production_flag=1` 的平均流量為 7.7943 m3/min、平均功率為 48.6388 kW。流量與功率相關係數 0.9982，代表夜間流量偏高很可能直接造成能耗浪費，下一步應比對夜間用氣許可、區域閥件與洩漏巡檢紀錄。

### Case 06：自動巡檢交班

FastMCP 顯示資料為 480 筆，時間範圍是 2026-05-01 08:00 到 2026-05-15 15:45，無訊號缺值。前 24 筆 `dryer_dew_point_c` 基準平均為 3.175 C，rolling scan 顯示 2026-05-09 10:00 與 2026-05-13 11:00 有明顯高露點窗口。`flow_m3_min` 與 `power_kw` 相關係數 0.9593，排氣溫度與功率相關係數 0.6487，因此交班摘要應同時標出乾燥機露點事件與負載/溫度連動。

## 學生交付格式

請輸出 5 句內繁體中文摘要，包含：

- 主要異常或管理重點
- 最值得注意的時間、機台狀態或操作情境
- 支撐判斷的訊號或 SQL/FastMCP 結果
- 合理原因或操作意義
- 下一步建議

## 延伸任務

1. 修改 `scripts/build_sqlite.py`，加入 Case 07、08 或 09，觀察多表資料如何整理。
2. 新增一張 `student_notes` 表，讓學生把 FastMCP 輸出與自己的摘要存回 SQLite。
3. 將 `fastmcp_findings` 改成由實際工具輸出 JSON 匯入，而不是手動整理文字。
