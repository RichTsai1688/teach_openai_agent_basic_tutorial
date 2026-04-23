# Case 01 Agent 任務腳本

## 目標
用統計工具先找出基準值與異常時段，再整理成設備異常判讀摘要。

## 建議直接給 AI 的任務
```text
請先使用 FastMCP 統計工具分析 `case_01_autonomous_sensing/advance/data_case_01_extended.csv`，並依序完成：

1. 用 `describe_dataset` 確認資料筆數、欄位與時間範圍。
2. 用 `baseline_profile` 計算：
   - vibration_mm_s
   - discharge_temp_c
   - motor_current_a
   - pressure_bar
   的前 8 筆基準值。
3. 用 `rolling_anomaly_scan` 掃描：
   - vibration_mm_s
   - discharge_temp_c
   找出最早異常時間。
4. 用 `correlation_report` 比較：
   - vibration_mm_s
   - discharge_temp_c
   - motor_current_a
   - pressure_bar
   的變動關係。

最後請輸出：
- 第一個需要注意的時間
- 哪些訊號一起偏離
- 最可能原因
- 建議先檢查的部位
- 5 句內的維修摘要
```
