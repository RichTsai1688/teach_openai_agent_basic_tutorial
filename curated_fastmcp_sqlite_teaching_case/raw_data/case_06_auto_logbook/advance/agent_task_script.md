# Case 06 Agent 任務腳本

## 目標
先用統計工具找出異常時段與重複出現的問題，再由 AI 整理成交班摘要。

## 建議直接給 AI 的任務
```text
請先使用 FastMCP 統計工具分析 `case_06_auto_logbook/advance/data_case_06_extended.csv`，並依序完成：

1. 用 `describe_dataset` 檢查資料筆數、時間範圍與缺值。
2. 用 `baseline_profile` 計算：
   - pressure_bar
   - discharge_temp_c
   - dryer_dew_point_c
   的基準值。
3. 用 `rolling_anomaly_scan` 掃描：
   - discharge_temp_c
   - dryer_dew_point_c
   - pressure_bar
4. 用 `correlation_report` 比較：
   - pressure_bar
   - discharge_temp_c
   - power_kw
   - flow_m3_min
   - dryer_dew_point_c

最後請輸出：
- 哪些時段需要優先追查
- 哪些異常可以先觀察
- 有沒有重複出現的模式
- 交班時最需要提醒的事項
- 4 句內的交班摘要
```
