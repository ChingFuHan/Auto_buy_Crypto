# Aggressive Breakout Backtest Report — Layer 1 (Hindsight)

生成時間：2026-04-30 05:36:58

---

## 1. Pre-flight Check

| 項目 | 值 |
|------|----|
| DB 資料範圍 | 2025-12-29 04:30:00 ~ 2026-04-30 05:15:00 |
| 總 rows | 6,090,184 |
| 總 symbols | 536 |
| 可能 delisted (>7d 無新 bar) | 0 個 |

> ⚠️ **生存者偏差警告**：DB 僅保有當前在線 symbol 的歷史資料。已下架的 symbol（尤其低市值幣）
> 不在 DB 中，回測結果偏正（pump-and-delist 後段損失無法計算）。

### Possibly Delisted
_無 (所有 symbol 近 7 天皆有資料)_

---

## 2. 策略參數（Layer 1 使用）

| 參數 | 值 |
|------|----|
| `ret_min` | 0.017 |
| `vol_multiple` | 2.0 |
| `range_pct_max` | 0.035 |
| `atr_pct_max` | 0.015 |
| `prior_runup_max` | 0.04 |
| `overheat_max` | 0.06 |
| `max_recent_green_bars` | 3 |
| `lookback` | 20 bars |
| `breakout_lookback` | 12 bars |
| Entry price | 15m bar close (hindsight) |
| Stop reference | 15m bar low |
| Cost deduction | 0.6% |

---

## 3. Bucket 定義與樣本數

**Universal base filter（每筆都要過）：**
- `ret_15m >= 0.017`
- `vol_ratio_15m >= 2.0`
- `breakout_15m = True`
- `prior_runup_15m <= 0.040`
- `recent_green_15m_bars <= 3`

| Bucket | 條件 | 樣本 N |
|--------|------|--------|
| **A** | range > 3.5% 且 ret ≤ 6%（range 擋） | 10755 |
| **B** | range ≤ 3.5% 且 ret > 6%（overheat 擋） | 232 |
| **C** | range > 3.5% 且 ret > 6%（兩者都擋） | 509 |
| **Baseline** | range ≤ 3.5% 且 ret ≤ 6%（主策略本來會抓） | 7725 |

---

## 4. Layer 1 回測結果（Hindsight — 用 finalized close 入場）

> ⚠️ **Lookahead bias 警告**：Layer 1 用 15m bar 收盤價作為入場價，實際上該收盤在 bar 結束才知道。
> 因此 Layer 1 結果為邊界上限，實盤表現會因 in-progress 入場點而低於此值。
> 若 Layer 1 expectancy < 0，直接 kill；> 0 才進 Layer 2。

### Bucket A  (N=10755)

| Metric | 4-bar (1h) | 16-bar (4h) | 96-bar (24h) |
|--------|-----------|------------|-------------|
| N (樣本數) | 10755 | 10751 | 10678 |
| Win rate | 29.6% | 34.5% | 35.8% |
| Mean return (扣 0.6%) | -0.721% | -0.686% | -0.607% |
| Median return | -1.034% | -1.343% | -2.087% |
| Std | 3.395% | 5.234% | 11.504% |
| MFE median | 1.364% | 2.437% | 4.877% |
| MFE p90 | 5.175% | 9.047% | 19.414% |
| MAE median | -1.626% | -2.703% | -5.140% |
| MAE p10 (worst 10%) | -3.973% | -6.414% | -12.382% |
| -3% stop hit rate | 19.5% | 44.9% | 73.8% |
| -5% stop hit rate | 5.3% | 18.7% | 51.6% |
| Bar-low stop hit rate | 24.2% | 50.9% | 77.2% |
| False stop rate (-3%) | 7.0% | 12.1% | 35.0% |
| False stop rate (bar-low) | 6.7% | 14.9% | 41.0% |
| Expectancy (成本後) | -0.721% | -0.686% | -0.607% |
| Sharpe (年化, rough) | -19.88 | -6.14 | -1.01 |

**決策：** ❌ **KILL** — Expectancy < 0 across all horizons. 不建議新增 aggressive 分支。

### Bucket B  (N=232)

| Metric | 4-bar (1h) | 16-bar (4h) | 96-bar (24h) |
|--------|-----------|------------|-------------|
| N (樣本數) | 232 | 232 | 232 |
| Win rate | 37.1% | 34.9% | 28.4% |
| Mean return (扣 0.6%) | -1.072% | -1.318% | -2.366% |
| Median return | -1.843% | -2.784% | -5.200% |
| Std | 7.328% | 9.168% | 11.999% |
| MFE median | 3.468% | 4.074% | 5.972% |
| MFE p90 | 10.509% | 18.346% | 25.790% |
| MAE median | -3.754% | -4.584% | -7.636% |
| MAE p10 (worst 10%) | -9.353% | -11.286% | -14.371% |
| -3% stop hit rate | 59.9% | 68.1% | 84.5% |
| -5% stop hit rate | 36.2% | 47.8% | 69.0% |
| Bar-low stop hit rate | 10.8% | 21.1% | 40.1% |
| False stop rate (-3%) | 28.8% | 32.3% | 43.4% |
| False stop rate (bar-low) | 12.0% | 8.2% | 9.7% |
| Expectancy (成本後) | -1.072% | -1.318% | -2.366% |
| Sharpe (年化, rough) | -13.70 | -6.73 | -3.77 |

**決策：** ❌ **KILL** — Expectancy < 0 across all horizons. 不建議新增 aggressive 分支。

### Bucket C  (N=509)

| Metric | 4-bar (1h) | 16-bar (4h) | 96-bar (24h) |
|--------|-----------|------------|-------------|
| N (樣本數) | 509 | 509 | 505 |
| Win rate | 41.5% | 36.9% | 34.9% |
| Mean return (扣 0.6%) | -0.284% | -0.384% | -1.040% |
| Median return | -1.187% | -1.797% | -4.158% |
| Std | 7.401% | 10.884% | 19.401% |
| MFE median | 3.981% | 5.744% | 9.045% |
| MFE p90 | 14.728% | 21.388% | 37.974% |
| MAE median | -3.660% | -4.932% | -8.834% |
| MAE p10 (worst 10%) | -9.126% | -13.004% | -19.556% |
| -3% stop hit rate | 58.3% | 70.5% | 83.8% |
| -5% stop hit rate | 32.2% | 48.7% | 70.7% |
| Bar-low stop hit rate | 10.8% | 25.5% | 51.1% |
| False stop rate (-3%) | 35.4% | 46.2% | 60.8% |
| False stop rate (bar-low) | 3.6% | 6.2% | 14.3% |
| Expectancy (成本後) | -0.284% | -0.384% | -1.040% |
| Sharpe (年化, rough) | -3.60 | -1.65 | -1.02 |

**決策：** ❌ **KILL** — Expectancy < 0 across all horizons. 不建議新增 aggressive 分支。

### Bucket Baseline  (N=7725)

| Metric | 4-bar (1h) | 16-bar (4h) | 96-bar (24h) |
|--------|-----------|------------|-------------|
| N (樣本數) | 7725 | 7725 | 7697 |
| Win rate | 26.3% | 29.9% | 37.4% |
| Mean return (扣 0.6%) | -0.747% | -0.868% | -0.551% |
| Median return | -0.955% | -1.197% | -1.385% |
| Std | 2.583% | 3.684% | 7.385% |
| MFE median | 0.975% | 1.554% | 3.644% |
| MFE p90 | 3.718% | 6.014% | 13.139% |
| MAE median | -1.214% | -2.006% | -3.648% |
| MAE p10 (worst 10%) | -3.057% | -4.668% | -8.580% |
| -3% stop hit rate | 10.4% | 28.8% | 59.0% |
| -5% stop hit rate | 2.3% | 8.0% | 33.1% |
| Bar-low stop hit rate | 16.5% | 41.6% | 68.8% |
| False stop rate (-3%) | 3.4% | 4.8% | 23.2% |
| False stop rate (bar-low) | 3.5% | 7.8% | 33.8% |
| Expectancy (成本後) | -0.747% | -0.868% | -0.551% |
| Sharpe (年化, rough) | -27.07 | -11.02 | -1.42 |

**決策：** ❌ **KILL** — Expectancy < 0 across all horizons. 不建議新增 aggressive 分支。

---

## 5. SOLVUSDT 個案對照

SOLVUSDT 2026-04-29 17:00 bar 在此回測中：
- Bucket: **C**
- bar_return: 9.897%
- window_range: 5.843%
- vol_ratio: 77.7x
- 4-bar: N/A (不足 4 bars)
- 16-bar: N/A (不足 16 bars)
- 96-bar: N/A (不足 96 bars)

---

## 6. 結論與建議

- **Bucket A** (N=10755): ❌ KILL — expectancy -0.607% < 0，無統計 edge。
- **Bucket B** (N=232): ❌ KILL — expectancy -1.072% < 0，無統計 edge。
- **Bucket C** (N=509): ❌ KILL — expectancy -0.284% < 0，無統計 edge。

---

## 附：回測規格說明

- **Layer 1 (本報告)**：用 finalized 15m bar close 作入場價，bar low 作止損參考。Fast feedback，有 hindsight bias。
- **Layer 2 (待定)**：若 Layer 1 pass，用 3m 子K 重建 in-progress 入場時序，消除 lookahead bias。
- **False stop rate 定義**：先 hit stop level → 同 horizon 內 high >= entry × (1 + 1R)。
- **Sharpe**：per-trade return 年化估算，非時序 Sharpe，僅供參考。
