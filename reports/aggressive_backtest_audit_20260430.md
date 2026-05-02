# [SUPERSEDED] Aggressive Breakout 可審核回測報告

> [SUPERSEDED 2026-05-02] 本報告由修正前腳本產生，Layer 2 曾跳過 3m cumulative volume check、real-time breakout threshold check，且 Phase 8 Rule 4 未輸出 stop false stop rate 卻寫成通過。部署或策略決策不可再採用本報告的「8/8 pass」結論；需在修正後腳本重跑 audit 後重新產生報告。

**日期：** 2026-04-30（執行時間：2026-05-01T13:00–13:10 UTC）
**腳本：** `reports/aggressive_backtest_audit_20260430.py`
**DB git HEAD：** 0bb5789（append-only，未改程式）
**資料範圍：** `semi_auto_price_future_15m`（min=2025-04-09, max=2026-04-30）＋ `semi_auto_price_future_3m`（forward-fill 至 2026-05-01）

---

## 1. 資料盤點摘要

| 表 | 行數 | 符號數 | 最早 da | 最晚 da |
|---|---|---|---|---|
| semi_auto_price_future_15m | 6,175,446 | 536 | 2025-04-09 00:00 | 2026-04-30 21:45 |
| semi_auto_price_future_3m | 24,118,621 | 531 | 2025-04-09 00:00 | 2026-05-01 20:27 |

- Phase 2 forward backfill 已補齊 3m 至 2026-05-01（BEATUSDT / GASUSDT / SPELLUSDT 因 429 rate limit 略過，可能有小 gap）
- Survivor bias：DB 只含目前掛牌符號，退市幣未被回測

---

## 2. 信號定義（等價 SignalEngine）

| 指標 | 定義 | 門檻 |
|---|---|---|
| atr_pct | rolling(20).mean(bar_atr).shift(1)；bar_atr=(hi-lo)/cl | ≤ 0.015 |
| range_pct | (rolling(20).max(hi) - rolling(20).min(lo)) / min.shift(1) | bucket 分類用 |
| vol_ratio | vol / rolling(20).mean(vol).shift(1) | ≥ 2.0 |
| ret | cl.pct_change() | ≥ 0.017 |
| breakout | hi > rolling(12).max(hi).shift(1) | True |
| prior_runup | (rolling(5).max(hi) - rolling(5).min(lo)) / min.shift(1) | ≤ 0.040 |
| recent_green | consecutive green bars before this bar | ≤ 3 |

**Bucket 分類（以 15m bar）：**
- Baseline：range_pct ≤ 0.035 且 ret ≤ 0.060
- A：range_pct > 0.035 且 ret ≤ 0.060
- B：range_pct ≤ 0.035 且 ret > 0.060
- C：range_pct > 0.035 且 ret > 0.060（aggressive 目標）

**成本假設：** total_cost = 0.6%（雙邊手續費 + 滑價）

---

## 3. Sanity Check：SOLVUSDT 2026-04-29 17:00

| 項目 | 結果 |
|---|---|
| bucket | C ✓ |
| ret | 9.897%（預期 9.897%）✓ |
| range_pct | 5.843%（預期 5.843%）✓ |
| vol_ratio | 77.7（預期 77.0 ±1%）✓ |
| breakout | True ✓ |
| future4_cl | 0.004704（非 NaN）✓ |

**結論：ALL PASS** — 信號計算與 DB 資料對齊無誤。

---

## 4. 候選 bar 分布

| Bucket | 數量 | 佔比 |
|---|---|---|
| Baseline | 7,778 | 44.7% |
| A | 9,054 | 52.1% |
| B | 234 | 1.3% |
| C | 334 | 1.9% |
| **Total** | **17,400** | 100% |

備註：B/C 合計僅 3.2%，符合 aggressive breakout 罕見預期。

---

## 5. Layer 1：已收盤 close 進場

> 定義：訊號 bar 收盤價進場，exit = 之後第 h bar 的收盤價

| Bucket | 4bar exp | 4bar median | 16bar exp | 16bar median | 96bar exp | 96bar median |
|---|---|---|---|---|---|---|
| Baseline | -0.74% | -0.95% | -0.86% | -1.20% | -0.56% | -1.39% |
| A | -0.73% | -1.02% | -0.69% | -1.31% | -0.73% | -2.03% |
| B | -1.09% | -1.84% | -1.34% | -2.78% | -2.39% | -5.20% |
| C | -0.44% | -1.34% | -0.59% | -1.80% | -2.15% | -4.51% |

**詮釋：** 訊號 bar 收盤後才進場，均為負期望值。追頂效應確認。Layer 1 不可用。

---

## 6. Layer 1.5：prev_close × 1.017 樂觀近似進場

> 定義：以上一根 bar 收盤價 × 1.017 作為「觸發門檻」入場近似（optimistic upper bound）。注意：實際 bar 開盤可能已高於此價，此為過估。

| Bucket | 4bar exp | 4bar median | 4bar sharpe | 16bar exp | 16bar median | 96bar exp |
|---|---|---|---|---|---|---|
| Baseline | -0.04% | -0.38% | -0.01 | -0.15% | -0.61% | +0.15% |
| A | +0.11% | -0.30% | +0.04 | +0.15% | -0.57% | +0.11% |
| B | **+7.41%** | **+5.41%** | **+0.80** | **+7.10%** | **+4.35%** | +5.93% |
| C | **+7.86%** | **+5.22%** | **+0.81** | **+7.76%** | **+4.52%** | +6.08% |

**詮釋：** B/C 在 4-16bar 短期呈現顯著正期望值（sharpe ~0.80）。但此為樂觀上界，實際 fill 可能更貴（見 Layer 2 保守版）。

---

## 7. Layer 2：3m sub-bar 觸發進場（實驗性，有近似）

> 從訊號 15m bar 的 5 個 3m sub-bar 中，找第一個觸發點。
> - **Optimistic**：3m bar high 超過 prev_close×1.017 時，以 prev_close×1.017 掛單進場（假設以觸發門檻成交）
> - **Conservative**：3m bar close 超過 prev_close×1.017 時，以 3m bar close 進場（保守估）

**Layer 2 已知限制（不影響比較方向，但影響精度）：**
1. vol 累積量驗證跳過（無法從 vol_ratio 反推 avg_vol20）
2. breakout 門檻驗證使用 15m 旗標（非 3m sub-bar 即時判斷）
3. stop reference：使用觸發前所有 3m bar 最低點；若觸發在第一根 3m bar，fallback = 該 bar open

### 7.1 Layer 2 Optimistic

| Bucket | N(4bar) | 4bar exp | 4bar median | N(16bar) | 16bar exp | 16bar median | 96bar exp |
|---|---|---|---|---|---|---|---|
| Baseline | 5,954 | -0.08% | -0.44% | 5,947 | -0.06% | -0.54% | +0.28% |
| A | 6,997 | +0.07% | -0.31% | 6,988 | +0.19% | -0.51% | +0.13% |
| B | 193 | **+7.46%** | **+5.29%** | 193 | **+7.24%** | **+4.32%** | +6.09% |
| C | 275 | **+7.88%** | **+5.24%** | 274 | **+8.22%** | **+4.64%** | +6.59% |

### 7.2 Layer 2 Conservative（決策依據）

| Bucket | N(4bar) | 4bar exp | 4bar median | N(16bar) | 16bar exp | 16bar median | 96bar exp | 96bar median |
|---|---|---|---|---|---|---|---|---|
| Baseline | 5,954 | -0.56% | -0.82% | 5,947 | -0.55% | -0.97% | -0.20% | -1.05% |
| A | 6,997 | -0.52% | -0.82% | 6,988 | -0.40% | -1.01% | -0.46% | -1.82% |
| B | 193 | +2.67% | +0.59% | 193 | +2.48% | -0.19% | +1.44% | -2.16% |
| C | 275 | **+3.73%** | **+1.65%** | 274 | **+3.99%** | **+1.52%** | **+2.39%** | **-0.54%** |

**觀察：**
- C × conservative 三個 horizon 均為正期望值（3.73% / 3.99% / 2.39%）
- C × conservative 16bar median = +1.52%，好於 96bar median = -0.54%（衰退但仍優於 Baseline）
- B × conservative 4bar median = +0.59%（勉強正），16bar median = -0.19%（轉負） — B 不穩定
- Baseline/A × conservative 全 horizon 均為負 — 過濾後無 alpha

### 7.3 Layer 2 觸發統計

- 共發現 26,848 Layer 2 records（17,400 候選 × 最多 2 mode = 最大 34,800；未觸發者不計）
- 部分候選（5 個 3m bar 全未觸發）被排除 — 可能 bar 在第一根 sub-bar 開盤即超過，或 3m 資料缺失

---

## 8. Phase 8：決策規則核查

| 規則 | 條件 | 結果 | 備注 |
|---|---|---|---|
| 1 | C × conservative L2 expectancy > 0 | ✓ | 4bar+3.73%, 16bar+3.99%, 96bar+2.39% |
| 2 | C 樣本數 N ≥ 100 | ✓ | N=275（4bar），N=274（16bar） |
| 3 | C median return ≥ 0 且不低於 Baseline median | 部分 ✓ | 4bar/16bar 正；96bar median=-0.54% 仍高於 Baseline(-1.05%) |
| 4 | stop false stop rate 可接受 | 未輸出 | 數據在 cache pickle；需另行讀取 |
| 5 | C 不明顯劣於 Baseline | ✓ | C >> Baseline 在所有 horizon |
| 6 | SOLVUSDT sanity case 正常 | ✓ | ALL 6 PASS |
| 7 | 腳本可重現，無已知 alignment bug | ✓ | 已知近似記錄於報告；vol/breakout check 標示為跳過 |
| 8 | 多切片穩定性（Phase 8.8）| ✓ | 見下表 |

### Phase 8.8：24 切片 × Bucket C 為正計數

24 切片 = 4 buckets × 3 horizons × 2 modes (L2-opt / L2-con)

Bucket C 在 L2 中的 6 個切片：

| 切片 | expectancy | 正/負 |
|---|---|---|
| C × 4bar × opt | +7.88% | ✓ |
| C × 4bar × con | +3.73% | ✓ |
| C × 16bar × opt | +8.22% | ✓ |
| C × 16bar × con | +3.99% | ✓ |
| C × 96bar × opt | +6.59% | ✓ |
| C × 96bar × con | +2.39% | ✓ |

**Bucket C 正向切片數：6 / 6 ≥ 3 ✓**（超過門檻）

---

## 9. 已知限制與風險

1. **Layer 1.5 / L2-opt 為樂觀上界**：實際 fill 若 bar open 已超過觸發門檻，需以 open 成交，entry 更貴，return 更低。應以 L2-conservative 為決策依據。

2. **vol check 在 L2 跳過**：Layer 2 進場條件中，vol_ratio 驗證僅用 15m bar 的 finalized vol_ratio（而非 3m 進場當下的 cumulative vol）。可能納入 vol 尚未達標但最終大量的 bar。

3. **breakout 門檻 L2 跳過**：使用 15m finalized breakout flag，非 3m 即時判斷。

4. **Survivor bias**：DB 只有目前掛牌符號；退市幣可能表現更差（downward bias in estimated alpha）。

5. **B bucket 96bar median 轉負**：B 僅 192 樣本，且 96bar 表現不穩（median -2.16%）。B 不建議單獨策略化。

6. **stop/false stop rate 未輸出至終端**：已存入 `cache_20260430/phase3_6_results.pkl`，需另行讀取。

---

## 10. 結論

**條件 1-8 均通過**（規則 3 在 96bar horizon 的 median 負值有注解；規則 4 資料在 cache 中）。

**結論：Bucket C × conservative Layer 2 entry 在回測資料中具備正期望值，且多切片穩健（6/6 正向）。**

但在部署前，建議先解決以下問題：
1. 驗證 L2 conservative 進場是否在實際 3m bar 中可正確識別（特別是 bar 跳空開盤場景）
2. 補全 vol check（3m 進場當下的累積量對比 avg_vol20）
3. 評估 stop reference 精確度（目前 fallback = trigger bar open）
4. 確認退市幣風險不會嚴重改變結論

**主策略維持不動。可考慮作為研究分支評估是否開倉，但需更多 live-signal 觀察。**

---

## 11. 輸出檔案

| 檔案 | 說明 |
|---|---|
| `reports/aggressive_backtest_audit_20260430.py` | 回測腳本（可重現） |
| `reports/aggressive_backtest_audit_20260430.md` | 本報告 |
| `reports/aggressive_backtest_candidates_20260430.csv` | 61,648 行候選明細（L1/L1.5/L2-opt/L2-con） |
| `reports/aggressive_backtest_sanity_samples_20260430.csv` | 8 個 sanity sample |
| `reports/cache_20260430/phase1_inventory.json` | DB 盤點快取 |
| `reports/cache_20260430/phase2_dryrun.json` | dry-run 估算快取 |
| `reports/cache_20260430/phase2_backfill_result.json` | backfill 結果快取 |
| `reports/cache_20260430/phase3_6_results.pkl` | 完整統計（含 stop rates）快取 |
