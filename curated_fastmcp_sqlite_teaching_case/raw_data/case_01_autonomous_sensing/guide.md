# 案例 01｜多感測器異常預警

## 你會練到什麼
這一題會用振動、溫度、電流、壓力四個訊號一起判斷異常。  
重點不是模型多複雜，而是學會把多個感測值整理成可解釋的風險分數。

## 情境
一台螺旋式空壓機在 2026-04-15 下午出現逐步升高的異常。  
請根據 `data_case_01.csv` 建立基準期，計算異常分數與風險分數，並找出最早的預警時間。

## 建議任務
```text
請讀取 data_case_01.csv，使用 Python（pandas + matplotlib）完成以下任務：
1. 把前 8 筆資料當作正常基準期。
2. 為 pressure_bar、discharge_temp_c、vibration_mm_s、motor_current_a 計算基準平均值。
3. 用簡單 z-score 概念建立 anomaly_score：
   anomaly_score = 0.45*z_vibration + 0.30*z_temp + 0.15*z_current + 0.10*z_pressure_drop
4. 再把 anomaly_score 轉成 0~100 的 risk_score。
5. 若 anomaly_score >= 3.5 判定為 alarm；
   若 2.0 <= anomaly_score < 3.5 判定為 early_warning；
   否則為 normal。
6. 畫出趨勢圖，並輸出：
   - 基準值
   - 第一個 early warning 時間
   - alarm 區間
   - 最高風險分數與時間
   - 最可能故障原因與維修建議
```

## 你可以檢查的答案
- 基準壓力平均：`7.0225 bar`
- 基準排氣溫度平均：`81.95 °C`
- 基準振動平均：`2.0375 mm/s`
- 基準電流平均：`95.9875 A`
- 第一個 early warning：`2026-04-15 14:20`
- alarm 區間：`2026-04-15 14:30 ~ 2026-04-15 15:20`
- alarm 筆數：`6`
- 最高風險分數：`95 / 100`
- 最可能原因：`軸承磨耗或潤滑不足`

## 延伸練習
1. 把圖表改成更適合投影片閱讀的版本。
2. 把結果整理成維修主管看得懂的 5 點摘要。
3. 比較「只看溫度」和「多感測器一起看」的差異。
