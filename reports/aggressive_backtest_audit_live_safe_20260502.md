# Aggressive Breakout 可審核回測報告（修正版）

> **本報告取代 `reports/aggressive_backtest_audit_20260430.md`（已標 [SUPERSEDED]）。**
> 前版報告的「8/8 pass」結論不可採用——Layer 2 當時跳過 3m cumulative volume check 與即時 breakout threshold check，且 Rule 4（stop false stop rate）未輸出。
> 本報告使用修正後 Layer 2 重跑，所有限制均已標示。

**日期：** 2026-05-02（執行時間：2026-05-02T07:16–07:17 UTC+8 推算）
**腳本：** `reports/aggressive_backtest_audit_20260430.py`（`audit-live-safe` 子命令）
**Run ID：** `live_safe_full_20260502`
**執行命令：**
```
nice -n 10 ionice -c2 -n7 python3 reports/aggressive_backtest_audit_20260430.py \
  audit-live-safe --batch-size 5 --sleep-seconds 1 --run-id live_safe_full_20260502
```
**git HEAD（執行時）：** 0bb5789（append-only，未改主交易程式）
**執行期間 live bot 狀態：** PID 162340 (`python3 main.py run`) 仍在跑，audit 峰值 RSS ≈ 423MB（遠低於舊全量 audit 約 14.5GB）

---

## 修正摘要（vs 前版報告）

| 項目 | 前版（SUPERSEDED）| 本版（修正後）|
|---|---|---|
| Layer 2 3m cumulative volume check | 跳過 | 同一採樣點成立才觸發 |
| Layer 2 即時 breakout threshold check | 跳過，用 15m finalized flag | 用 15m 原始 breakout_threshold，3m cum_high > threshold |
| Layer 2 ret 條件 | 15m bar 標準 | 3m 採樣點 ret ≥ 0.017 同步成立 |
| Rule 4（stop false stop rate）| 未輸出，仍寫 pass | 已輸出（見第 9 節）|
| L2 con C 4bar exp | +3.73% | **+3.20%** |
| L2 con C 16bar exp | +3.99% | **+3.45%** |
| L2 con C 96bar exp | +2.39% | **+1.89%** |
| L2 con C 96bar median | -0.54% | **-1.07%** |
| Phase 8 結論 | 8/8 pass（不可採信）| 7/8 pass（Rule 3 在 96bar 部分通過）|

---

## 1. 資料盤點摘要

| 資料 | 說明 |
|---|---|
| `semi_auto_price_future_15m` | 6,175,446 rows（含 536 符號，2025-04-09 至 2026-04-30） |
| `semi_auto_price_future_3m` | forward-fill 至 2026-05-01（BEATUSDT / GASUSDT / SPELLUSDT 略過）|
| 候選 bar | 17,439 筆（audit-live-safe SELECT，按 symbol batch 5，sleep 1s）|
| Layer 2 records | 26,848 筆（L2 opt + con 合計，不含未觸發）|

- Survivor bias：DB 僅含目前掛牌符號，退市幣未被回測。
- 本次 audit 不跑 backfill、不寫 DB、不連 Binance private/account/order API。

---

## 2. 信號定義（等價 SignalEngine）

| 指標 | 定義 | 門檻 |
|---|---|---|
| atr_pct | rolling(20).mean(bar_atr).shift(1)；bar_atr=(hi-lo)/cl | ≤ 0.015 |
| range_pct | (rolling(20).max(hi) − rolling(20).min(lo)) / min.shift(1) | bucket 分類用 |
| vol_ratio | vol / rolling(20).mean(vol).shift(1) | ≥ 2.0 |
| ret | cl.pct_change() | ≥ 0.017 |
| breakout | hi > rolling(12).max(hi).shift(1) | True |
| prior_runup | (rolling(5).max(hi) − rolling(5).min(lo)) / min.shift(1) | ≤ 0.040 |
| recent_green | 連續上漲 bars，不含本根 | ≤ 3 |

**Bucket 分類（以 15m bar）：**

| Bucket | range_pct | ret | 說明 |
|---|---|---|---|
| Baseline | ≤ 0.035 | ≤ 0.060 | 主策略通過樣本 |
| A | > 0.035 | ≤ 0.060 | range 超標但漲幅未極端 |
| B | ≤ 0.035 | > 0.060 | 漲幅極端但 range 正常 |
| C | > 0.035 | > 0.060 | range 與漲幅均極端（SOLVUSDT 屬此）|

**成本假設：** total_cost = 0.6%（雙邊手續費 + 滑價），已含於 expectancy。

---

## 3. Layer 2 定義（修正後）

Layer 2 從訊號 15m bar 的最多 5 個 3m sub-bar 中，找第一個觸發點。

**觸發條件（三者必須在同一 3m 採樣點同時成立）：**
1. **cumulative volume**：累積 3m vol / avg_vol20 ≥ 2.0
2. **breakout**：3m bar 累積 high > 15m bar 的 breakout_threshold（rolling(12).max(hi).shift(1)）
3. **ret**：3m bar close vs 前一 15m bar close 的漲幅 ≥ 0.017

**Layer 2 模式：**
- **Optimistic**：觸發點 3m bar high 超過 prev_close × 1.017 時，以 prev_close × 1.017 進場（樂觀上界）
- **Conservative**：觸發點 3m bar close 進場（保守估，決策依據）

**Stop reference：** 觸發前所有 3m bar 最低點；若觸發在第一根，fallback = 該 bar open。

---

## 4. 候選 bar 分布

| Bucket | L1 數量 | 佔比 | L2-con 數量（4bar） |
|---|---|---|---|
| Baseline | 7,797 | 44.7% | 5,956 |
| A | 9,073 | 52.0% | 7,000 |
| B | 235 | 1.3% | 193 |
| C | 334 | 1.9% | **275** |
| **Total** | **17,439** | 100% | **26,848（L2 records）** |

備註：L2 N < L1 N，因部分 15m bar 的 5 個 3m sub-bar 均未同時滿足三條件（約 18% C 樣本未觸發 L2）。

---

## 5. Layer 1：已收盤 close 進場（參考）

> 訊號 bar 收盤後才進場，為最悲觀基準（追頂偏差最大）。

| Bucket | N | 4bar exp | 4bar med | 16bar exp | 16bar med | 96bar exp | 96bar med |
|---|---|---|---|---|---|---|---|
| Baseline | 7,797 | -0.74% | -0.95% | -0.85% | -1.20% | -0.55% | -1.39% |
| A | 9,073 | -0.73% | -1.02% | -0.69% | -1.30% | -0.73% | -2.03% |
| B | 235 | -1.09% | -1.82% | -1.34% | -2.78% | -2.37% | -5.20% |
| C | 334 | -0.44% | -1.34% | -0.60% | -1.80% | -2.15% | -4.51% |

**詮釋：** L1 全負，追頂效應確認。不可作為決策依據；需看 L1.5 / L2。

---

## 6. Layer 1.5：prev_close × 1.017 樂觀近似進場（參考）

> 以上一根 bar 收盤 × 1.017 作近似，為樂觀上界（若 bar open 已超過此價，實際 fill 更貴）。

| Bucket | N | 4bar exp | 4bar med | 4bar sharpe | 16bar exp | 16bar med | 96bar exp | 96bar med |
|---|---|---|---|---|---|---|---|---|
| Baseline | 7,797 | -0.04% | -0.38% | -0.01 | -0.15% | -0.61% | +0.15% | -0.74% |
| A | 9,073 | +0.11% | -0.30% | +0.04 | +0.16% | -0.57% | +0.11% | -1.29% |
| B | 235 | **+7.42%** | **+5.47%** | **+0.80** | **+7.11%** | **+4.36%** | +5.95% | +1.72% |
| C | 334 | **+7.86%** | **+5.22%** | **+0.81** | **+7.74%** | **+4.50%** | +6.08% | +2.51% |

---

## 7. Layer 2 Optimistic（樂觀上界）

| Bucket | N(4bar) | 4bar exp | 4bar med | N(16bar) | 16bar exp | 16bar med | 96bar exp | 96bar med |
|---|---|---|---|---|---|---|---|---|
| Baseline | 5,956 | -0.11% | -0.46% | 5,956 | -0.10% | -0.56% | +0.25% | -0.64% |
| A | 7,000 | -0.11% | -0.47% | 7,000 | +0.01% | -0.67% | -0.05% | -1.47% |
| B | 193 | **+7.40%** | **+5.29%** | 193 | **+7.18%** | **+4.17%** | +6.05% | +1.49% |
| C | 275 | **+7.38%** | **+4.66%** | 275 | **+7.69%** | **+4.25%** | +6.09% | +2.30% |

---

## 8. Layer 2 Conservative（決策依據）

> **修正後**：volume / breakout / ret 必須在同一 3m 採樣點同時成立。

| Bucket | N(4bar) | 4bar exp | 4bar med | 4bar sharpe | N(16bar) | 16bar exp | 16bar med | 96bar exp | 96bar med |
|---|---|---|---|---|---|---|---|---|---|
| Baseline | 5,956 | -0.59% | -0.84% | -0.21 | 5,956 | -0.58% | -0.99% | -0.23% | -1.09% |
| A | 7,000 | -0.65% | -0.93% | -0.22 | 7,000 | -0.52% | -1.12% | -0.58% | -1.90% |
| B | 193 | +2.63% | +0.58% | +0.31 | 193 | +2.44% | -0.35% | +1.41% | -2.18% |
| C | **275** | **+3.20%** | **+1.22%** | **+0.36** | **275** | **+3.45%** | **+1.17%** | **+1.89%** | **-1.07%** |

**觀察：**
- C × conservative 三個 horizon 均為正期望值（**+3.20% / +3.45% / +1.89%**），低於修正前（3.73% / 3.99% / 2.39%）
- C 4bar / 16bar median 為正（+1.22% / +1.17%）；**96bar median = -1.07%（負）**
- 96bar C median（-1.07%）僅略高於 Baseline（-1.09%），差異 0.02%——長期持有優勢極弱
- B conservative 16bar median 轉負（-0.35%），B 不穩定
- Baseline / A 全負 — 非 aggressive bar 在此層無 alpha

---

## 9. Stop / False Stop 統計（L2 Conservative）

> Rule 4 在前版「未輸出」，本版已完整提供。

| Bucket | horizon | stop_3pct% | stop_5pct% | stop_ref% | false_stop_ref% |
|---|---|---|---|---|---|
| Baseline | 4bar | 10.5% | 2.2% | 17.6% | 7.8% |
| Baseline | 16bar | 26.9% | 7.3% | 41.2% | 19.6% |
| Baseline | 96bar | 56.1% | 31.8% | 67.7% | 33.1% |
| C | **4bar** | 29.1% | 13.8% | **9.5%** | **4.4%** |
| C | **16bar** | 41.1% | 25.1% | **20.0%** | **9.5%** |
| C | **96bar** | 67.2% | 52.0% | **44.3%** | **16.2%** |

**解讀：**
- Bucket C 的 false_stop_reference_rate 低於同 horizon 的 Baseline（4.4% vs 7.8%；9.5% vs 19.6%；16.2% vs 33.1%）——C 的 stop reference（bar_low）較少被「假擊穿後又拉回」。
- stop_3pct_rate 高（C 4bar 29.1%、96bar 67.2%），代表 C 的 3m sub-bar 觸發進場後 -3% 止損命中率高；若採 3% 固定止損需謹慎計算 sizing。
- stop_reference_rate（基於 bar_low）在 4bar 為 9.5%，意味多數短線持有不會跌穿 trigger sub-bar 的最低點。

---

## 10. Phase 8：決策規則核查（修正後）

| 規則 | 條件 | 結果 | 備注 |
|---|---|---|---|
| 1 | C × conservative L2 exp > 0，三個 horizon | ✓ PASS | 4bar +3.20%、16bar +3.45%、96bar +1.89% |
| 2 | C L2 樣本 N ≥ 100 | ✓ PASS | N=275（4/16bar）、N=271（96bar）|
| 3 | C median ≥ 0（4/16bar）；96bar median ≥ Baseline | 部分通過 | 4bar +1.22% ✓、16bar +1.17% ✓；**96bar -1.07%（負）**，僅略優於 Baseline -1.09%（差距 0.02%）|
| 4 | false_stop_reference_rate 可接受 | 4/16bar ✓，96bar 邊界 | 4bar 4.4% ✓、16bar 9.5% ✓、96bar 16.2%（邊界）|
| 5 | C L2 con 優於 Baseline | ✓ PASS | 各 horizon C >> Baseline |
| 6 | 腳本可重現，L2 無已知對齊 bug | ✓ PASS | 修正後 volume / breakout / ret 同採樣點；已知近似記錄於第 11 節 |
| 7 | Sharpe > 0（4/16bar）| ✓ PASS | 4bar sharpe +0.36、16bar +0.29；96bar +0.12（邊界正）|
| 8 | 多切片穩定性：C × L2 正向切片 ≥ 3 | ✓ PASS | 6/6 正向（見下表）|

**整體：7/8 PASS（前版「8/8」已作廢）**

Rule 3 在 96bar 部分通過（median 負，但仍略優於 Baseline）。96bar 長期持有訊號強度不足，不建議持有逾 16bar。

### Phase 8.8：Bucket C × L2 切片穩定性

| 切片 | exp | 正/負 |
|---|---|---|
| C × 4bar × opt | +7.38% | ✓ |
| C × 4bar × con | +3.20% | ✓ |
| C × 16bar × opt | +7.69% | ✓ |
| C × 16bar × con | +3.45% | ✓ |
| C × 96bar × opt | +6.09% | ✓ |
| C × 96bar × con | +1.89% | ✓ |

**Bucket C 正向切片：6 / 6 ≥ 3 ✓**

---

## 11. 已知限制與風險

1. **修正後 L2 expectancy 低於前版**：舊版 4bar +3.73% → 修正後 +3.20%（-0.53%）；16bar +3.99% → +3.45%（-0.54%）；96bar +2.39% → +1.89%（-0.50%）。舊版高估因跳過即時 volume / breakout check，已納入修正。

2. **96bar median 仍為負（-1.07%）**：長期持有優勢弱，且 96bar stop_3pct_rate = 67.2%；除非有明確 profit-taking / trailing stop 機制，不建議持倉逾 16bar。

3. **L2 進場仍有近似**：3m volume 以 `cum_vol / avg_vol20` 累積，avg_vol20 來自 15m bar；3m 資料與 15m bar 時間軸對齊用 bar_idx 換算，可能有 1 根 3m bar 誤差。

4. **stop reference 近似**：以觸發前所有 3m bar 最低點作 stop reference；若 trigger 在第一根 sub-bar，fallback = open，非精確反映 in-progress 實際 low。

5. **Survivor bias**：DB 僅含目前掛牌符號。退市幣（通常表現更差）未計入，alpha 可能高估。

6. **L2 未觸發樣本排除（~18% C）**：334 個 C 候選中 59 個未觸發 L2（三條件在 5 根 3m sub-bar 內從未同時成立）。這批樣本的實盤情況未被評估。

7. **非 live 統計**：回測無滑價動態模型、無盤口深度、無多符號同時觸發衝突。live 實際 fill 可能較回測更差。

---

## 12. 結論

**Bucket C × conservative Layer 2 修正後仍具正期望值（4bar +3.20%，16bar +3.45%，96bar +1.89%），6/6 切片正向穩定。**

**但：**
- 修正後數字低於舊報告；舊「8/8 pass」結論不可採用。
- 96bar median = -1.07%，Rule 3 在 96bar 部分不通過。
- 本輪整體評估：**7/8 PASS**（非 8/8）。

**部署判定：**
- **不可直接部署至 live 主策略**。
- 可進入 **shadow / prototype 設計審查**：紙上交易、獨立小倉模擬、或 shadow 訊號 log 觀察，目標是在 live 環境累積 N ≥ 50 個真實 C-bucket 觸發樣本後再評估。
- 主策略 15m Baseline 邏輯維持不動，不修改 `config.py`、`pump_system/`、`.env`。

**下一步建議（prototype 設計前置條件）：**
1. 確認 L2 conservative 進場在 live in-progress 3m bar 中可正確識別（bar 跳空開盤場景的 fill 處理）
2. 補全 3m cumulative volume 在 live-feed 中的計算路徑
3. 設計 shadow 訊號 log（只 log，不下單），觀察 6–12 週 C-bucket 觸發頻率與後續走勢
4. 確認 sizing / stop 方案能容納 stop_3pct_rate = 29.1%（4bar）的現實

---

## 13. 輸出檔案

| 檔案 | 說明 |
|---|---|
| `reports/aggressive_backtest_audit_20260430.py` | 回測腳本（含 `audit-live-safe` 子命令）|
| `reports/aggressive_backtest_audit_live_safe_20260502.md` | 本報告（修正版）|
| `reports/aggressive_backtest_audit_20260430.md` | 前版報告（已標 [SUPERSEDED]，不可採信 8/8 結論）|
| `reports/cache_20260430/live_safe_full_20260502/candidates_15m_live_safe_full_20260502.csv` | 17,439 行候選明細 |
| `reports/cache_20260430/live_safe_full_20260502/layer2_live_safe_full_20260502.csv` | 26,848 行 L2 records |
| `reports/cache_20260430/live_safe_full_20260502/results_live_safe_full_20260502.json` | 完整統計（L1/L1.5/L2-opt/L2-con + stop rates）|
| `reports/cache_20260430/live_safe_full_20260502/results_live_safe_full_20260502.pkl` | 同上（pickle 格式）|
