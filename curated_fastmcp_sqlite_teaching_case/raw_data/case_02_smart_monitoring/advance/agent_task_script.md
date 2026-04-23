# Case 02 Agent 任務腳本

## 目標
先用統計工具比較夜間流量分布，再由 AI 判斷夜間漏氣與浪費程度。

## 建議直接給 AI 的任務
```text
請先使用 FastMCP 統計工具分析 `case_02_smart_monitoring/advance/data_case_02_extended.csv`，並依序完成：

1. 用 `describe_dataset` 檢查資料時間範圍與欄位。
2. 用 `group_compare` 比較 `production_flag` 在 `flow_m3_min` 的差異。
3. 用 `group_compare` 比較 `production_flag` 在 `power_kw` 的差異。
4. 用 `rolling_anomaly_scan` 掃描 `flow_m3_min`，找出夜間異常偏高的時間。
5. 用 `correlation_report` 比較：
   - flow_m3_min
   - power_kw
   - pressure_bar

最後請輸出：
- 是否存在明顯夜間漏氣
- 最早異常夜間時段
- 夜間流量與功率的關係
- 可能是漏氣還是其他合法用氣
- 5 句內的管理摘要
```
