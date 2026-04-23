# AI Agent 統計解讀流程

這套流程的重點，不是讓 AI 直接猜答案，而是讓 AI 先用工具查證，再做解讀。

## 建議流程
1. 先描述資料集
2. 計算基準值
3. 掃描離群點或趨勢漂移
4. 比較不同群組
5. 再由 AI 寫出結論

## 範例流程

### Step 1
用 `describe_dataset` 看資料大小、時間範圍、缺值情況。

### Step 2
用 `baseline_profile` 取得前 24 筆或前幾天的基準值。

### Step 3
用 `rolling_anomaly_scan` 找最近明顯偏離基準的時間點。

### Step 4
如果資料中有群組欄位，例如 `production_flag`、`shift`、`machine_id`，用 `group_compare` 比較差異。

### Step 5
如果想看多個訊號是否一起變化，用 `correlation_report`。

## 最後請 AI 輸出
- 這份資料的主要異常是什麼
- 最早出現在哪個時間段
- 哪些訊號最值得注意
- 有哪些合理原因
- 建議下一步怎麼查

## Case 01~09 可以怎麼套

### Case 01｜自主感測
- 先用 `describe_dataset` 看時間範圍與欄位
- 再用 `baseline_profile` 看 vibration、temperature、current、pressure 的基準值
- 最後用 `rolling_anomaly_scan` 找最早偏移時段

### Case 02｜智慧監控
- 先用 `describe_dataset`
- 再用 `group_compare` 比較 `production_flag` 在 flow、power 的差異
- 最後用 `rolling_anomaly_scan` 找夜間流量異常偏高的時間

### Case 03｜AI 調控
- 先用 `describe_dataset`
- 再用 `baseline_profile` 看 demand 與 baseline power
- 最後用 `correlation_report` 比 demand、ambient、power 的關係

### Case 04｜自動報表
- 先用 `describe_dataset`
- 再用 `group_compare` 比 `production_flag` 在 flow、power 的差異
- 最後用 `rolling_anomaly_scan` 找值得追蹤的異常日

### Case 05｜預測維護
- 先用 `describe_dataset`
- 再用 `group_compare` 比 `machine_id` 在 vibration、temperature、oil delta p 的差異
- 最後用 `correlation_report` 幫 AI 整理維修優先順序

### Case 06｜自動巡檢
- 先用 `describe_dataset`
- 再用 `baseline_profile` 看 pressure、temperature、dew point 的基準值
- 最後用 `rolling_anomaly_scan` 找重複異常時段

### Case 07｜多機排程
- 先用 `describe_dataset`
- 再用 `group_compare` 比 `production_mode` 在 demand、tariff、line pressure 的差異
- 最後用 `rolling_anomaly_scan` 找高需求、高電價與 guardrail 集中的時段

### Case 08｜漏氣派工
- 先對 leak survey 用 `describe_dataset`
- 再用 `group_compare` 比 `zone` 在 isolation drop、ultrasound、operator reports 的差異
- 最後對 validation 用 `baseline_profile` 與 `correlation_report` 看修前修後變化

### Case 09｜夜班自治
- 先用 `describe_dataset`
- 再用 `baseline_profile` 看 demand、buffer、min pressure、dew point 的基準值
- 最後用 `rolling_anomaly_scan` 找需要人工核准或升級處理的夜班時段

## 學生可以直接照著問

### 通用版
```text
請先使用 FastMCP 統計工具分析這份資料，依序完成：
1. describe_dataset
2. baseline_profile 或 group_compare
3. rolling_anomaly_scan
4. correlation_report

最後請用繁體中文整理：
- 主要異常或重點
- 最早需要注意的時間
- 最值得追的訊號
- 合理原因
- 建議下一步
```

### Case 07~09 進階版
```text
請先不要直接下結論，先用 FastMCP 工具查證。

- 如果是 Case 07，請先找 demand、tariff、line pressure 同時偏高的時段，再整理排程建議。
- 如果是 Case 08，請先比較各 zone 的 leak 指標，再整理派工順序與修後驗證摘要。
- 如果是 Case 09，請先找 buffer、dew point 或 vibration 風險升高的夜班時段，再整理自治與人工核准建議。

最後請用繁體中文寫成 5 句可直接交付的摘要。
```
