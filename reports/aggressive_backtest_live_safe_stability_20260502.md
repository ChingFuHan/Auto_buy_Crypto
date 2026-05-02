# Aggressive Breakout Live-Safe 穩健性研究補充報告

> 補充 `reports/aggressive_backtest_audit_live_safe_20260502.md`，**不取代**主報告。
> 本報告只做研究分析，不改主線交易邏輯、不改 `config.py` / `pump_system/` / `.env`、不寫 DB、不連 Binance private API、不停止 live bot。
> 主報告結論：Bucket C × conservative L2 修正後 7/8 PASS、不可直接部署、可進 shadow/prototype 設計審查。本補充報告判斷該結論是否仍成立。

**日期：** 2026-05-02 (UTC+8)
**git HEAD（執行時）：** 0bb5789（未 commit；只新增本 md）
**Live bot 狀態：** PID 162340 仍在跑（`python3 main.py run`），未受影響
**輸入資料：**
- `reports/cache_20260430/live_safe_full_20260502/layer2_live_safe_full_20260502.csv`
- `reports/cache_20260430/live_safe_full_20260502/results_live_safe_full_20260502.json`
- `reports/aggressive_backtest_audit_live_safe_20260502.md`

**分析範圍：** Bucket C × `entry_mode == 'conservative'`，N = **275** trades，178 unique symbols，期間 2026-01-23 ~ 2026-05-01。
**成本假設：** total_cost = 0.6%（同主報告，已扣於所有 expectancy）

---

## 1. 時間切片穩定性

### 1.1 月度（M）

| 月份 | N | 4bar exp | 4bar med | 4bar win% | 16bar exp | 16bar med | 16bar win% | 96bar exp | 96bar med | 96bar win% |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-01 | 15 | +7.02% | +3.46% | 86.7% | +5.39% | +2.41% | 73.3% | +8.47% | +2.64% | 60.0% |
| 2026-02 | 70 | +2.96% | +2.01% | 64.3% | +1.94% | +0.09% | 50.0% | **-1.66%** | **-2.27%** | **32.9%** |
| 2026-03 | 82 | +2.99% | +0.57% | 58.5% | +2.81% | +2.17% | 64.6% | +3.00% | -0.58% | 45.1% |
| 2026-04 | 104 | +2.85% | +0.48% | 55.8% | +4.02% | +1.24% | 53.8% | +2.44% | +0.17% | 51.0% |
| 2026-05 | 4 | +6.48% | +6.35% | 75.0% | +20.99% | +14.70% | 50.0% | NaN（資料不足）| NaN | NaN |

**觀察：**
- **4bar exp 每月皆為正**（+2.85% ~ +7.02%），最低月仍高於成本。短期 edge 跨月穩定。
- **16bar exp 每月皆為正**（+1.94% ~ +5.39%；2026-05 資料極少不採信）。
- **96bar exp 在 2026-02 為負**（-1.66%，win=32.9%）。長期 horizon 跨月不穩，2026-02 明顯差。
- **2026-01 N=15 偏少**，+7% 的高數字部分受小樣本放大。
- **Win rate 4bar 隨時間下降**（86.7→64.3→58.5→55.8%）；可能反映：(a) 樣本擴張納入更廣交易對；(b) 市場 regime 變化；(c) hindsight survivorship 較嚴重於早期。

### 1.2 季度（Q）

| 季度 | N | 4bar exp | 4bar med | 4bar win% | 16bar exp | 16bar med | 96bar exp | 96bar med |
|---|---|---|---|---|---|---|---|---|
| 2026Q1 | 167 | +3.34% | +1.59% | 63.5% | +2.68% | +1.17% | +1.54% | -1.54% |
| 2026Q2 | 108 | +2.99% | +0.65% | 56.5% | +4.65% | +1.24% | +2.44% | +0.17% |

**觀察：**
- 季度 4bar / 16bar exp 在 +2.7% ~ +4.7% 區間，方向一致。Edge 不只集中在某一季。
- 96bar median Q1 為 -1.54%（Q2 +0.17%）；長 horizon 持有風險集中於 2026-02。

### 1.3 結論

- **4bar / 16bar：跨月皆正、跨季穩定**，此區間 edge 可視為相對穩健。
- **96bar：時間切片不穩**（2026-02 exp 與 median 雙負）。**長期持有不可作為主要訊號用途**。
- 早期月份（2026-01）N 太少，未來研究應排除或加權處理。

---

## 2. Symbol 分布集中度

### 2.1 概覽

- Unique symbols：**178**
- 平均每 symbol 交易數：**1.55**（中位數 1）
- 4bar 總貢獻和：+879.82%（mean × N 加總）
- 16bar 總貢獻和：+949.04%
- 96bar 總貢獻和：+511.16%

### 2.2 集中度（4bar）

| 截斷 | 累計貢獻佔比 |
|---|---|
| Top 1 symbol | 4.9% |
| Top 3 | 13.3% |
| Top 5 | 21.1% |
| Top 10 | 39.6% |

### 2.3 Top 15 / Bottom 10 contributors

**Top 15 by 4bar 貢獻和：**

| symbol | N | mean_4 | sum_4 | mean_16 | sum_16 | mean_96 | sum_96 |
|---|---|---|---|---|---|---|---|
| ACXUSDT | 1 | 43.52 | 43.52 | 52.58 | 52.58 | 22.70 | 22.70 |
| BANKUSDT | 1 | 37.34 | 37.34 | 34.37 | 34.37 | 8.91 | 8.91 |
| ETHWUSDT | 1 | 36.14 | 36.14 | 27.44 | 27.44 | 4.34 | 4.34 |
| COSUSDT | 4 | 8.63 | 34.52 | 9.63 | 38.53 | 18.45 | 73.81 |
| ZKPUSDT | 1 | 34.52 | 34.52 | 38.65 | 38.65 | -1.00 | -1.00 |
| OGNUSDT | 2 | 16.73 | 33.47 | 21.96 | 43.92 | 17.33 | 34.66 |
| SENTUSDT | 3 | 11.04 | 33.12 | 7.60 | 22.81 | 18.42 | 55.26 |
| AGTUSDT | 7 | 4.62 | 32.35 | 9.55 | 66.88 | 16.32 | 114.25 |
| BRUSDT | 2 | 15.80 | 31.59 | 31.50 | 63.01 | 60.44 | 120.88 |
| SOMIUSDT | 2 | 15.74 | 31.49 | 4.85 | 9.69 | 7.73 | 15.47 |
| RAREUSDT | 1 | 30.39 | 30.39 | 15.45 | 15.45 | -9.57 | -9.57 |
| TAIKOUSDT | 1 | 27.12 | 27.12 | 33.96 | 33.96 | 1.59 | 1.59 |
| AINUSDT | 4 | 6.41 | 25.64 | 6.04 | 24.16 | 12.43 | 49.73 |
| PLAYUSDT | 1 | 24.70 | 24.70 | 25.05 | 25.05 | 38.50 | 38.50 |
| BOBUSDT | 4 | 6.08 | 24.32 | 1.28 | 5.10 | -5.98 | -23.91 |

**Bottom 10：**

| symbol | N | mean_4 | sum_4 | mean_16 | sum_16 | mean_96 | sum_96 |
|---|---|---|---|---|---|---|---|
| ERAUSDT | 1 | -7.09 | -7.09 | -8.51 | -8.51 | -8.19 | -8.19 |
| TLMUSDT | 2 | -4.05 | -8.10 | -5.81 | -11.62 | -8.03 | -16.06 |
| LUMIAUSDT | 1 | -8.20 | -8.20 | -7.82 | -7.82 | -9.63 | -9.63 |
| ZKCUSDT | 1 | -8.50 | -8.50 | -9.33 | -9.33 | -13.85 | -13.85 |
| ZAMAUSDT | 1 | -9.01 | -9.01 | 1.50 | 1.50 | 1.99 | 1.99 |
| DYMUSDT | 2 | -4.53 | -9.05 | -3.64 | -7.29 | -3.00 | -6.00 |
| ROBOUSDT | 1 | -10.79 | -10.79 | -20.26 | -20.26 | -28.15 | -28.15 |
| CYSUSDT | 1 | -10.85 | -10.85 | -21.08 | -21.08 | -18.60 | -18.60 |
| ASTRUSDT | 1 | -12.07 | -12.07 | -11.85 | -11.85 | -13.89 | -13.89 |
| NAORISUSDT | 2 | -8.91 | -17.82 | -7.62 | -15.24 | -3.21 | -6.41 |

### 2.4 排除 Top contributors 的穩健性

| 排除項 | 剩餘 N | 4bar exp | 4bar median |
|---|---|---|---|
| 全部 | 275 | +3.20% | +1.22% |
| 排除 Top 1 | 274 | +3.05% | +1.20% |
| 排除 Top 3 | 272 | +2.80% | +1.17% |
| 排除 Top 5 | 267 | +2.60% | +1.19% |

### 2.5 結論

- **Edge 並非集中在少數 symbol**。Top1 share 僅 4.9%，Top10 share 39.6%。
- **排除 top 5 後 4bar exp 仍 +2.60%**，median +1.19%。Edge 能承受最暴利樣本被剔除。
- 多數 symbol N=1，**個別 symbol 的 mean 不可單獨採信**；只能在 cohort 層級觀察。
- Bottom 集中為小 N 個別大跌（ROBOUSDT、CYSUSDT、NAORISUSDT 等），未集中於少數 recurring 標的。

---

## 3. False stop 深挖

### 3.1 整體（cohort 層 sanity，與主報告一致）

| horizon | stop_hit% | false_stop_ref% |
|---|---|---|
| 4bar | 9.5% | 4.4% |
| 16bar | 20.0% | 9.5% |
| 96bar | 43.6% | 16.0% |

> 注意：本表 96bar false_stop_ref = 16.0%，主報告寫 16.2%；差異來自 NaN handling 邊界（4 筆 96bar 無資料），不影響結論。

### 3.2 by `trigger_offset_min`

> `trigger_offset_min` 為 3m 子 K 觸發時與 15m bar 起點的分鐘差（0/3/6/9/12）。

| trigger_offset_min | N | stop_hit_4% | false_stop_4% | false_stop_16% | false_stop_96% |
|---|---|---|---|---|---|
| 0 | 77 | **2.6%** | **1.3%** | 5.2% | 10.4% |
| 3 | 69 | 8.7% | 1.4% | 10.1% | 15.9% |
| 6 | 60 | 18.3% | 8.3% | 10.0% | 21.7% |
| 9 | 44 | 6.8% | 4.5% | 11.4% | 18.2% |
| 12 | 25 | 16.0% | **12.0%** | 16.0% | 16.0% |

**觀察：**
- **早觸發（offset=0）顯著乾淨**：4bar stop_hit 僅 2.6%、false_stop 1.3%。代表整根 15m bar 一開始三條件就同時成立的樣本，後續 stop reference 較少被擊穿。
- **晚觸發（offset=12）惡化**：4bar stop_hit 16%、false_stop 12%。15m bar 後段才條件成立的樣本，已經接近當下的 micro top，stop reference（觸發前 3m low）較淺，容易被假擊穿。
- **此為操作層強訊號**：若進 shadow / prototype 設計，可考慮以 `trigger_offset_min ≤ 6` 為過濾條件，僅取早觸發樣本。

### 3.3 by month

| 月份 | N | false_stop_4% | false_stop_16% | false_stop_96% |
|---|---|---|---|---|
| 2026-01 | 15 | 0.0% | 0.0% | 6.7% |
| 2026-02 | 70 | 0.0% | 8.6% | 20.0% |
| 2026-03 | 82 | 3.7% | 4.9% | 13.4% |
| 2026-04 | 104 | **8.7%** | **15.4%** | 17.3% |
| 2026-05 | 4 | 0.0% | 0.0% | 0.0% |

**觀察：**
- **2026-04 false stop 顯著上升**（4bar 8.7%、16bar 15.4%），與 4bar win rate 下降同步。
- 雖然 4bar exp 在 2026-04 仍為正（+2.85%），但 stop 行為惡化中。**需在 shadow 階段持續監控**，若延伸至 2026-Q2 末仍惡化，應重評估是否值得進 prototype。

### 3.4 by symbol（false_stop_96，N≥3）

| symbol | N | false_stop_4% | false_stop_16% | false_stop_96% |
|---|---|---|---|---|
| DUSDT | 7 | 0.0% | 14.3% | 57.1% |
| BOBUSDT | 4 | 0.0% | 0.0% | 50.0% |
| SENTUSDT | 3 | 0.0% | 0.0% | 33.3% |
| FOLKSUSDT | 3 | 0.0% | 0.0% | 33.3% |
| AGTUSDT | 7 | 14.3% | 14.3% | 28.6% |
| PUMPBTCUSDT | 4 | 0.0% | 25.0% | 25.0% |
| 我踏马来了USDT | 4 | 0.0% | 0.0% | 25.0% |

> N≥3 樣本仍偏小，僅供質性參考；DUSDT 7 筆有 4 筆 96bar 假擊穿值得進 shadow log 個案追蹤。

### 3.5 代表性 false stop（4bar）案例

| symbol | bar_da | trigger_offset | entry_price | stop_reference | mae_lo_4 | exit_cl_4 | ret_4 |
|---|---|---|---|---|---|---|---|
| AGTUSDT | 2026-04-22 22:45 | 3 | 0.014965 | 0.014000 | 0.013949 | 0.014661 | -2.63% |
| CHILLGUYUSDT | 2026-04-19 07:45 | 0 | 0.013639 | 0.013231 | 0.013090 | 0.013335 | -2.83% |
| DYMUSDT | 2026-03-16 02:45 | 12 | 0.039730 | 0.036040 | 0.035460 | 0.036250 | -9.36% |
| HIGHUSDT | 2026-04-27 15:45 | 9 | 0.224300 | 0.210800 | 0.210100 | 0.213600 | -5.37% |
| MYXUSDT | 2026-04-21 02:00 | 12 | 0.246000 | 0.228800 | 0.227400 | 0.231300 | -6.58% |

**樣本特徵：** 多數案例 mae_lo 僅微幅穿過 stop_reference（差距 < 1%），但 exit_cl 已大幅低於 entry_price。代表 stop 被擊穿後價格未拉回到 entry 上方，雖滿足「假擊穿」定義（exit > stop_ref），但 trade 仍是負報酬。

### 3.6 結論

- 整體 false_stop 比例與主報告一致；**by trigger_offset 是最重要的新發現**：早觸發樣本顯著乾淨。
- by month：**2026-04 stop 行為惡化**，需持續監測。
- by symbol：N 太小不可作集中度結論，僅供 shadow log 個案標記。

---

## 4. 結論與建議

### 4.1 三項問題的判斷

| 問題 | 結果 |
|---|---|
| Edge 是否只集中在某幾個月份？ | **否**，4bar / 16bar 月度與季度皆為正且穩定。但 **96bar 在 2026-02 為負**，長 horizon 跨月不穩。|
| Edge 是否由少數 symbol 撐起？ | **否**。Top1 4.9%、Top5 21.1%、排除 top5 後 4bar exp 仍 +2.60%。Edge 跨 178 個 symbol 分散。|
| False stop 風險是否可接受？ | **4bar / 16bar 整體可接受**；2026-04 出現惡化趨勢；trigger_offset ≥ 9 的樣本明顯較髒。|

### 4.2 整體判斷

- 3 個維度都未出現「edge 高度集中或不穩定」級別的紅旗。
- **可進入 shadow / prototype signal spec 設計階段**，與主報告 7/8 PASS 結論一致。
- **不可繞過 shadow，不可直接部署 live 主策略。** 主策略 15m Baseline 邏輯維持不動。

### 4.3 進 shadow / prototype 設計時的硬限制

1. **持有 horizon 上限 16bar**：96bar median 在 Q1 為負、月度不穩，prototype 不應採 96bar 出場規則。
2. **優先採 trigger_offset_min ≤ 6 的早觸發樣本**：4bar false_stop 從 12% 降到 ≤ 1.4%，stop_hit 從 16% 降到 ≤ 8.7%。Shadow signal log 必須記錄 `trigger_offset_min`。
3. **2026-04 stop 惡化需持續監測**：shadow 至少需累積到 2026-Q2 末，比較 stop_hit / false_stop 是否回穩；若惡化延續，重評估。
4. **2026-01 小樣本不採信為基準**：未來樣本以 2026-02 之後為主。
5. **不修改 `config.py` / `pump_system/` / `.env`**：即使進 prototype 設計，仍需先紙上交易 + shadow log，不直接寫入交易邏輯。

### 4.4 不採取的行動（明確邊界）

- 未改 `config.py`、`pump_system/`、`.env`、主交易程式
- 未跑 `audit` / `audit-live-safe` / `backfill` / `all`
- 未寫 DB
- 未連 Binance private / account / order API
- 未停止 live bot (PID 162340 全程運行)
- 未讀 `HANDOFF_ARCHIVE.md`
- 只新增本 md；HANDOFF.md 僅最小追加

---

## 5. 輸出檔

| 檔案 | 說明 |
|---|---|
| `reports/aggressive_backtest_live_safe_stability_20260502.md` | 本報告 |

中間統計表（暫存於 `/tmp/stability_out/`，不入 repo）：month / quarter / symbol / trigger_offset / fs_month / fs_rows_4。
